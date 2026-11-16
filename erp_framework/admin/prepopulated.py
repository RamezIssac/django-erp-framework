"""
Prepopulated inlines: a "sheet" of one inline row per entity (supplier, client,
employee...), with live row computations, totals and keyboard-friendly entry.

The whole behaviour lives on the inline, using public Django admin hooks only
(``get_extra`` / ``get_min_num`` / ``get_max_num`` / ``get_formset`` /
``formfield_for_dbfield``). No ``ModelAdmin`` mixin is required::

    class StockCountLineInline(PrepopulatedInlineMixin, admin.TabularInline):
        model = StockCountLine
        can_delete = False
        prepopulation_field = "product"
        prepopulation_queryset = Product.objects.filter(active=True).order_by("code")
        computed_fields = {
            "value": "quantity * unit_price",
        }
        total_fields = ("quantity", "value", ("total_weight", None, "quantity * unit_weight"))
        total_summaries = (("Avg price", "value / quantity"),)

        def get_prepopulation_extra_data(self, request, obj, entity_ids):
            return {pk: {"unit_price": 10} for pk in entity_ids}

Notes
-----
* On GET, entities that do not have a row yet are appended as extra forms,
  with ``{prepopulation_field: pk, **extra_data[pk]}`` as initial data.
* On POST the entity value is posted (hidden input) without initial data, so
  *every* prepopulated row is saved, including untouched ones. This is the
  long-standing behaviour journals rely on (e.g. an employee row with no
  changes still records a normal work day).
* ``computed_fields`` are display-only: their inputs are disabled, posted
  values are ignored, and the model is expected to compute them on save.

Spreadsheet behaviour
---------------------
* ``fast_rendering`` (default): rows are rendered by a lean template whose
  cells are built in Python (``erp_grid`` template tag) instead of one widget
  template per input. A 500-row x 15-column sheet renders ~10x faster and
  ~6x smaller. Locked sheets only; unlocked inlines keep the theme template.
* Keyboard (prepopulated_inline.js): arrows move between cells/rows, Enter /
  Shift+Enter next/previous cell, PageUp/PageDown jump 10 rows, Ctrl+Up/Down
  first/last row, F2 edits inside a cell, Escape reverts the cell.
  Numeric inputs are rendered as ``inputmode="decimal"`` text inputs, so arrow
  keys and the mouse wheel never alter values.
* ``autosave = True`` saves a row when one of its cells is committed (blur /
  change) through ``GridAutosaveAdminMixin``'s endpoint (requires that mixin
  on the parent ``ModelAdmin``). See ``GridAutosaveAdminMixin``.
"""

import json
from urllib.parse import urlencode

from django import forms
from django.contrib.admin.utils import unquote
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import models, transaction
from django.forms.models import _get_foreign_key
from django.http import Http404, HttpResponse, HttpResponseNotAllowed, JsonResponse, QueryDict
from django.urls import NoReverseMatch, path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext

GRID_TEMPLATE = "erp_framework/admin/edit_inline/prepopulated_tabular.html"
FAST_GRID_TEMPLATE = "erp_framework/admin/edit_inline/prepopulated_grid.html"
DEFAULT_INLINE_TEMPLATE = "admin/edit_inline/tabular.html"
HTMX_JS = "erp_framework/vendor/htmx/htmx.min.js"


class ReadOnlyEntityWidget(forms.Widget):
    """
    Render a FK value as plain text plus a hidden input.

    Labels are resolved from a ``{pk: label}`` dict built once when the form
    field is created (once per request), instead of rendering a full
    ``<select>`` with every choice on every row.
    """

    def __init__(self, queryset=None, labels=None, attrs=None):
        super().__init__(attrs)
        if labels is None:
            labels = {str(obj.pk): str(obj) for obj in (queryset if queryset is not None else [])}
        self.labels = labels

    def render(self, name, value, attrs=None, renderer=None):
        attrs = self.build_attrs(self.attrs, attrs)
        if value in (None, ""):
            return mark_safe('<span class="erp-readonly-entity">—</span>')
        return format_html(
            '<span class="erp-readonly-entity">{}</span>'
            '<input type="hidden" name="{}" value="{}" id="{}">',
            self.labels.get(str(value), str(value)),
            name,
            value,
            attrs.get("id", ""),
        )


class PrepopulatedInlineMixin:
    """Mixin for ``InlineModelAdmin`` subclasses. See module docstring."""

    #: FK field name on the inline model that holds the entity.
    prepopulation_field = None
    #: Entities to prepopulate (one row each). ``None`` disables prepopulation.
    prepopulation_queryset = None
    #: Render the entity as read-only text + hidden input.
    prepopulation_readonly = True
    #: Lock the sheet: hide "Add another" and delete links (min = max = rows).
    lock_prepopulated_rows = True

    #: ``{field_name: "expression"}`` evaluated per row in the browser, in
    #: declaration order. Expressions may use other field names of the same
    #: row, numbers, ``+ - * /`` and parentheses.
    computed_fields = {}
    #: Sums shown in the sticky totals bar. Items are either a field name, or a
    #: ``(key, label, "row expression")`` tuple summing an expression per row
    #: (``label=None`` keeps the sum hidden, e.g. as input for a summary).
    total_fields = ()
    #: ``[(label, "expression")]`` evaluated over the totals (identifiers are
    #: field names from ``total_fields``). Division by zero yields 0.
    total_summaries = ()
    #: Enter key moves to the next editable input instead of submitting.
    enter_as_tab = True
    #: Render rows with the lean Python-built grid (locked sheets only).
    fast_rendering = True
    #: Render numeric inputs as ``inputmode="decimal"`` text inputs.
    numeric_text_inputs = True
    #: Save a row as soon as one of its cells is committed (blur/change).
    #: Requires ``GridAutosaveAdminMixin`` on the parent ``ModelAdmin``.
    autosave = False

    @property
    def media(self):
        js = ("erp_framework/js/prepopulated_inline.js",)
        if self.autosave:
            js = (HTMX_JS,) + js
        return super().media + forms.Media(
            js=js,
            css={"all": ("erp_framework/css/prepopulated_inline.css",)},
        )

    def __init__(self, parent_model, admin_site):
        super().__init__(parent_model, admin_site)
        # Wrap whatever tabular template the theme/inline uses.
        self.grid_base_template = self.template or DEFAULT_INLINE_TEMPLATE
        if self.fast_rendering and self.lock_prepopulated_rows:
            self.template = FAST_GRID_TEMPLATE
        else:
            self.template = GRID_TEMPLATE

    # ── Prepopulation ────────────────────────────────────────────────────

    def get_prepopulation_queryset(self, request, obj=None):
        """Return the entity queryset, or ``None`` for no prepopulation."""
        if self.prepopulation_queryset is None:
            return None
        return self.prepopulation_queryset.all()

    def get_prepopulation_extra_data(self, request, obj, entity_ids):
        """
        Hook: extra initial data for new rows, as ``{entity_pk: {field: value}}``.
        ``entity_ids`` only contains entities that don't have a row yet.
        """
        return {}

    def get_prepopulation_state(self, request, obj=None):
        """
        Return ``(initial_rows, existing_row_count)`` computed once per request.
        """
        cache = request.__dict__.setdefault("_erp_prepopulation_cache", {})
        key = (id(self), getattr(obj, "pk", None))
        if key not in cache:
            cache[key] = self._build_prepopulation_state(request, obj)
        return cache[key]

    def get_prepopulated_initial(self, request, obj=None):
        return self.get_prepopulation_state(request, obj)[0]

    def _build_prepopulation_state(self, request, obj):
        if not self.prepopulation_field:
            raise ImproperlyConfigured(f"{type(self).__name__}.prepopulation_field is required.")

        existing_ids = []
        if obj is not None and obj.pk is not None:
            fk = _get_foreign_key(self.parent_model, self.model, fk_name=self.fk_name)
            existing_ids = list(
                self.get_queryset(request)
                .filter(**{fk.name: obj})
                .values_list(f"{self.prepopulation_field}_id", flat=True)
            )

        queryset = self.get_prepopulation_queryset(request, obj)
        if queryset is None:
            return [], len(existing_ids)

        existing = set(existing_ids)
        entity_ids = [pk for pk in queryset.values_list("pk", flat=True) if pk not in existing]
        extra = self.get_prepopulation_extra_data(request, obj, entity_ids) or {}
        initial = [{self.prepopulation_field: pk, **extra.get(pk, {})} for pk in entity_ids]
        return initial, len(existing_ids)

    # ── Formset sizing ───────────────────────────────────────────────────

    def get_extra(self, request, obj=None, **kwargs):
        return len(self.get_prepopulated_initial(request, obj))

    def get_min_num(self, request, obj=None, **kwargs):
        if not self.lock_prepopulated_rows:
            return super().get_min_num(request, obj, **kwargs)
        initial, existing = self.get_prepopulation_state(request, obj)
        return existing + len(initial)

    def get_max_num(self, request, obj=None, **kwargs):
        if not self.lock_prepopulated_rows:
            return super().get_max_num(request, obj, **kwargs)
        initial, existing = self.get_prepopulation_state(request, obj)
        return existing + len(initial)

    def get_formset(self, request, obj=None, **kwargs):
        FormSet = super().get_formset(request, obj, **kwargs)
        inline, req = self, request

        class PrepopulatedFormSet(FormSet):
            def __init__(self, *args, **kw):
                is_bound = (args[0] if args else kw.get("data")) is not None
                if not is_bound and "initial" not in kw:
                    initial = inline.get_prepopulated_initial(req, obj)
                    if initial:
                        kw["initial"] = initial
                super().__init__(*args, **kw)

            def _saved_by_entity(self):
                """Saved items of this document not posted as initial forms, by entity pk."""
                if not hasattr(self, "_erp_saved_by_entity"):
                    self._erp_saved_by_entity = {}
                    if self.instance is not None and self.instance.pk is not None:
                        pk_name = self.model._meta.pk.name
                        claimed = {
                            str(self.data.get(f"{self.add_prefix(i)}-{pk_name}") or "")
                            for i in range(self.initial_form_count())
                        }
                        entity_attr = f"{inline.prepopulation_field}_id"
                        for item in self.get_queryset().order_by("pk"):
                            if str(item.pk) not in claimed:
                                self._erp_saved_by_entity.setdefault(str(getattr(item, entity_attr)), item)
                return self._erp_saved_by_entity

            def _construct_form(self, i, **kwargs):
                # One row per entity: if an *extra* (new) row's entity is already
                # saved for this document (e.g. by autosave, another tab, or a
                # page that was open before), bind the form to that item so
                # Save updates it instead of inserting a duplicate.
                if self.is_bound and i >= self.initial_form_count() and inline.prepopulation_field:
                    entity = self.data.get(f"{self.add_prefix(i)}-{inline.prepopulation_field}")
                    existing = self._saved_by_entity().pop(str(entity), None) if entity else None
                    if existing is not None:
                        kwargs["instance"] = existing
                return super()._construct_form(i, **kwargs)

        PrepopulatedFormSet.__name__ = FormSet.__name__
        return PrepopulatedFormSet

    # ── Fields ───────────────────────────────────────────────────────────

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield is None:
            return formfield

        if self.prepopulation_readonly and db_field.name == self.prepopulation_field:
            # Replaces the RelatedFieldWidgetWrapper too: no add/change links.
            formfield.widget = ReadOnlyEntityWidget(queryset=getattr(formfield, "queryset", None))

        if db_field.name in self.computed_fields:
            formfield.disabled = True
            formfield.required = False
            formfield.widget.attrs.update({"tabindex": "-1", "class": "erp-computed"})

        widget = formfield.widget
        if self.numeric_text_inputs and getattr(widget, "input_type", None) == "number":
            # Text + inputmode: no spinners, and arrows/wheel never change values.
            widget.input_type = "text"
            widget.attrs.pop("step", None)
            widget.attrs["inputmode"] = "decimal"
            widget.attrs["autocomplete"] = "off"
            widget.attrs["class"] = " ".join(filter(None, (widget.attrs.get("class"), "erp-num")))
        return formfield

    # ── Browser config ───────────────────────────────────────────────────

    def _decimals(self, name):
        try:
            field = self.model._meta.get_field(name)
        except FieldDoesNotExist:
            return None
        if isinstance(field, models.DecimalField):
            return field.decimal_places
        if isinstance(field, (models.IntegerField,)):
            return 0
        return None

    def _label(self, name):
        try:
            return capfirst(self.model._meta.get_field(name).verbose_name)
        except FieldDoesNotExist:
            return capfirst(name.replace("_", " "))

    def _totals_config(self):
        totals = []
        for item in self.total_fields:
            if isinstance(item, str):
                totals.append({"name": item, "label": self._label(item)})
            else:
                key, label, expr = item
                totals.append({"name": key, "label": label, "expr": expr, "hidden": label is None})
        return totals

    def get_autosave_url(self):
        opts = self.parent_model._meta
        try:
            return reverse(f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_grid_autosave")
        except NoReverseMatch:
            raise ImproperlyConfigured(
                f"{type(self).__name__}.autosave requires GridAutosaveAdminMixin on the "
                f"{opts.model_name} ModelAdmin."
            )

    @property
    def grid_config(self):
        totals = self._totals_config()
        names = set(self.computed_fields) | {t["name"] for t in totals}
        config = {
            "computed": [[name, expr] for name, expr in self.computed_fields.items()],
            "totals": totals,
            "summaries": [{"label": label, "expr": expr} for label, expr in self.total_summaries],
            "decimals": {name: self._decimals(name) for name in names},
            "enterAsTab": self.enter_as_tab,
        }
        if self.autosave:
            config["autosave"] = {
                "url": self.get_autosave_url(),
                "messages": {
                    "saving": gettext("Saving…"),
                    "saved": gettext("All changes saved"),
                    "failed": gettext("%(count)s rows not saved"),
                    "error": gettext("Could not save this row."),
                },
            }
        return config


class HeaderLookupAdminMixin:
    """
    ``ModelAdmin`` mixin for documents identified by a set of header fields
    (e.g. ``("doc_date", "shift")`` for a daily journal).

    When one of ``header_lookup_fields`` changes in the change form, htmx asks
    the ``header-lookup/`` endpoint whether a document with those values
    already exists, and navigates to it. This avoids typing a whole sheet only
    to hit a ``unique_together`` error.

    With ``reload_add_on_header_change = True`` the add page is reloaded with
    the header values as GET initial data, so prepopulated inlines that depend
    on the header (``request.GET``) can be rebuilt.
    """

    header_lookup_fields = ()
    reload_add_on_header_change = False

    @property
    def media(self):
        media = super().media
        if self.header_lookup_fields:
            media += forms.Media(js=("erp_framework/vendor/htmx/htmx.min.js",))
        return media

    def _header_lookup_url_name(self):
        opts = self.model._meta
        return f"{opts.app_label}_{opts.model_name}_header_lookup"

    def get_urls(self):
        urls = super().get_urls()
        if not self.header_lookup_fields:
            return urls
        return [
            path(
                "header-lookup/",
                self.admin_site.admin_view(self.header_lookup_view),
                name=self._header_lookup_url_name(),
            )
        ] + urls

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        if not self.header_lookup_fields:
            return form
        url = reverse(f"{self.admin_site.name}:{self._header_lookup_url_name()}")
        include = ",".join(f"[name='{name}']" for name in self.header_lookup_fields)
        vals = json.dumps({"_object_id": str(obj.pk) if obj is not None and obj.pk else ""})
        for name in self.header_lookup_fields:
            field = form.base_fields.get(name)
            if field is None:
                continue
            field.widget.attrs.update(
                {
                    "hx-get": url,
                    "hx-trigger": "change",
                    "hx-include": include,
                    "hx-vals": vals,
                    "hx-swap": "none",
                }
            )
        return form

    def get_header_lookup_queryset(self, request, cleaned):
        return self.get_queryset(request).filter(**cleaned)

    def header_lookup_view(self, request):
        no_content = HttpResponse(status=204)
        form_class = super().get_form(request, None)
        cleaned, raw = {}, {}
        for name in self.header_lookup_fields:
            value = request.GET.get(name)
            field = form_class.base_fields.get(name)
            if not value or field is None:
                return no_content
            try:
                cleaned[name] = field.clean(value)
            except ValidationError:
                return no_content
            raw[name] = value

        object_id = request.GET.get("_object_id") or None
        queryset = self.get_header_lookup_queryset(request, cleaned)
        if object_id:
            queryset = queryset.exclude(pk=object_id)
        existing = queryset.first()

        opts = self.model._meta
        target = None
        if existing is not None and self.has_view_or_change_permission(request, existing):
            target = reverse(
                f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_change",
                args=(existing.pk,),
            )
        elif object_id is None and self.reload_add_on_header_change:
            target = reverse(f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_add")
            target += "?" + urlencode(raw)

        if target is None:
            return no_content
        response = HttpResponse("")
        response["HX-Redirect"] = target
        return response


class GridAutosaveAdminMixin:
    """
    ``ModelAdmin`` mixin: per-row autosave endpoint for prepopulated inlines
    declared with ``autosave = True``.

    The browser POSTs one row (its inputs, named as in the page formset) to
    ``grid-autosave/`` with ``_prefix`` (formset prefix), ``_row`` (row prefix,
    e.g. ``items-12``) and ``_object_id`` (empty on the add page).

    * On the add page the parent is created from the posted main form (as
      "Save" would). If its unique header already exists (e.g. same date and
      shift, see ``HeaderLookupAdminMixin.header_lookup_fields``), that
      document is used instead.
    * The row is matched to its saved item by (parent, prepopulation entity),
      so it is created once and updated afterwards, never duplicated.
    * The row goes through a one-form formset and ``self.save_formset()``, so
      validation and the admin's save hooks run exactly as on a full save.

    JSON response: ``{ok, objectId, changeUrl, created, pk, values}`` or
    ``{ok: false, errors}`` with HTTP 400.
    """

    def _grid_autosave_url_name(self):
        opts = self.model._meta
        return f"{opts.app_label}_{opts.model_name}_grid_autosave"

    def get_urls(self):
        return [
            path(
                "grid-autosave/",
                self.admin_site.admin_view(self.grid_autosave_view),
                name=self._grid_autosave_url_name(),
            )
        ] + super().get_urls()

    # ── Parent ───────────────────────────────────────────────────────────

    def _autosave_header_fields(self):
        return getattr(self, "header_lookup_fields", ()) or ()

    def _autosave_get_or_create_parent(self, request):
        """Return ``(obj, created, errors)`` for an add-page autosave."""
        ModelForm = self.get_form(request, None, change=False)
        form = ModelForm(request.POST, request.FILES)
        if form.is_valid():
            obj = self.save_form(request, form, change=False)
            self.save_model(request, obj, form, change=False)
            self.log_addition(request, obj, self.construct_change_message(request, form, None, add=True))
            return obj, True, None

        # Already exists (unique header)? Continue on that document.
        header = self._autosave_header_fields()
        if header and all(name in form.cleaned_data for name in header):
            lookup = {name: form.cleaned_data[name] for name in header}
            existing = self.get_queryset(request).filter(**lookup).first()
            if existing is not None and self.has_change_permission(request, existing):
                return existing, False, None
        return None, False, form.errors

    # ── Row ──────────────────────────────────────────────────────────────

    def _autosave_inline(self, request, obj, prefix):
        for inline in self.get_inline_instances(request, obj):
            if not getattr(inline, "autosave", False):
                continue
            FormSet = inline.get_formset(request, obj)
            if FormSet.get_default_prefix() == prefix:
                return inline, FormSet
        return None, None

    @staticmethod
    def _autosave_formset_data(post, prefix, row, existing_pk):
        """Remap the posted row ``<row>-<field>`` to form 0 of a 1-form formset."""
        data = QueryDict(mutable=True)
        data.update(
            {
                f"{prefix}-TOTAL_FORMS": "1",
                f"{prefix}-INITIAL_FORMS": "1" if existing_pk else "0",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "1000",
            }
        )
        start = f"{row}-"
        for key in post:
            if key.startswith(start):
                data.setlist(f"{prefix}-0-{key[len(start):]}", post.getlist(key))
        data[f"{prefix}-0-id"] = str(existing_pk or "")
        return data

    def grid_autosave_view(self, request):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        prefix = request.POST.get("_prefix", "")
        row = request.POST.get("_row", "")
        index = row[len(prefix) + 1:] if row.startswith(prefix + "-") else ""
        if not prefix or not index.isdigit():
            return JsonResponse({"ok": False, "errors": {"__all__": ["Invalid row."]}}, status=400)

        object_id = request.POST.get("_object_id") or None
        with transaction.atomic():
            created = False
            if object_id:
                obj = self.get_object(request, unquote(object_id))
                if obj is None:
                    raise Http404
                if not self.has_change_permission(request, obj):
                    raise PermissionDenied
                # Serialise concurrent saves on the same document.
                list(self.model._default_manager.select_for_update().filter(pk=obj.pk).values_list("pk"))
            else:
                if not self.has_add_permission(request):
                    raise PermissionDenied
                obj, created, errors = self._autosave_get_or_create_parent(request)
                if obj is None:
                    return JsonResponse({"ok": False, "errors": errors}, status=400)

            inline, FormSet = self._autosave_inline(request, obj, prefix)
            if inline is None:
                raise Http404

            entity_field = inline.prepopulation_field
            fk = _get_foreign_key(self.model, inline.model, fk_name=inline.fk_name)
            try:
                entity = FormSet.form.base_fields[entity_field].clean(request.POST.get(f"{row}-{entity_field}"))
            except (KeyError, ValidationError):
                return JsonResponse({"ok": False, "errors": {entity_field: ["Invalid entity."]}}, status=400)

            existing = (
                inline.get_queryset(request).filter(**{fk.name: obj, entity_field: entity}).order_by("pk").first()
            )
            if existing is not None:
                if not inline.has_change_permission(request, obj):
                    raise PermissionDenied
            elif not inline.has_add_permission(request, obj):
                raise PermissionDenied

            queryset = inline.get_queryset(request).filter(pk=existing.pk if existing else None)
            formset = FormSet(
                self._autosave_formset_data(request.POST, prefix, row, existing.pk if existing else None),
                prefix=prefix,
                instance=obj,
                queryset=queryset,
            )
            if not formset.is_valid():
                errors = dict(formset.forms[0].errors) if formset.forms else {}
                if formset.non_form_errors():
                    errors["__all__"] = list(formset.non_form_errors())
                transaction.set_rollback(True)
                return JsonResponse({"ok": False, "errors": errors}, status=400)

            ParentForm = self.get_form(request, obj, change=True)
            self.save_formset(request, ParentForm(instance=obj), formset, change=True)
            item = formset.forms[0].instance if formset.forms[0].instance.pk else existing

        values = {}
        if item is not None and item.pk:
            display = FormSet.form(instance=item, prefix=row)
            for name in display.fields:
                bound = display[name]
                values[name] = bound.field.widget.format_value(bound.value())
        opts = self.model._meta
        return JsonResponse(
            {
                "ok": True,
                "objectId": str(obj.pk),
                "changeUrl": reverse(
                    f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_change", args=(obj.pk,)
                ),
                "created": created,
                "pk": item.pk if item is not None else None,
                "values": values,
            }
        )

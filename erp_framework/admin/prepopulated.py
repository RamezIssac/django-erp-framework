"""
Prepopulated inlines: a "sheet" of one inline row per entity (supplier, client,
employee...), with live row computations, totals and keyboard-friendly entry.

The whole behaviour lives on the inline, using public Django admin hooks only
(``get_extra`` / ``get_min_num`` / ``get_max_num`` / ``get_formset`` /
``formfield_for_dbfield``). No ``ModelAdmin`` mixin is required::

    class MilkJournalItemInline(PrepopulatedInlineMixin, admin.TabularInline):
        model = MilkJournalItem
        can_delete = False
        prepopulation_field = "supplier"
        prepopulation_queryset = Supplier.objects.filter(active=True).order_by("slug")
        computed_fields = {
            "b_value": "b_quan * b_price",
            "total_value": "b_value + g_value",
        }
        total_fields = ("b_quan", "b_value", "total_value")

        def get_prepopulation_extra_data(self, request, obj, entity_ids):
            return {pk: {"b_price": 10} for pk in entity_ids}

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
"""

import json
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured, ValidationError
from django.db import models
from django.forms.models import _get_foreign_key
from django.http import HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import capfirst

GRID_TEMPLATE = "erp_framework/admin/edit_inline/prepopulated_tabular.html"
DEFAULT_INLINE_TEMPLATE = "admin/edit_inline/tabular.html"


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

    @property
    def media(self):
        return super().media + forms.Media(
            js=("erp_framework/js/prepopulated_inline.js",),
            css={"all": ("erp_framework/css/prepopulated_inline.css",)},
        )

    def __init__(self, parent_model, admin_site):
        super().__init__(parent_model, admin_site)
        # Wrap whatever tabular template the theme/inline uses.
        self.grid_base_template = self.template or DEFAULT_INLINE_TEMPLATE
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

    @property
    def grid_config(self):
        totals = self._totals_config()
        names = set(self.computed_fields) | {t["name"] for t in totals}
        return {
            "computed": [[name, expr] for name, expr in self.computed_fields.items()],
            "totals": totals,
            "summaries": [{"label": label, "expr": expr} for label, expr in self.total_summaries],
            "decimals": {name: self._decimals(name) for name in names},
            "enterAsTab": self.enter_as_tab,
        }


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

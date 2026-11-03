Prepopulated inlines (data-entry sheets)
=======================================

Daily journals often need *one inline row per entity*: one row per supplier in a
milk-collection sheet, one row per client on a distribution line, one row per
employee. ``erp_framework.admin.prepopulated`` provides this on the **inline**,
using public Django admin hooks only.

.. code-block:: python

    from django.contrib import admin
    from erp_framework.admin.prepopulated import HeaderLookupAdminMixin, PrepopulatedInlineMixin


    class MilkJournalItemInline(PrepopulatedInlineMixin, admin.TabularInline):
        model = MilkJournalItem
        extra = 0
        can_delete = False

        prepopulation_field = "supplier"                       # FK on the inline model
        prepopulation_queryset = Supplier.objects.filter(active=True).order_by("slug")

        # Display-only, computed live in the browser (the model computes them on save)
        computed_fields = {
            "b_value": "b_quan * b_price",
            "total_value": "b_value + g_value",
        }
        # Sticky totals bar: field names, or (key, label, "row expression");
        # label=None keeps a helper sum hidden.
        total_fields = ("b_quan", "b_value", ("b_quan_fat", None, "b_quan * b_fat"))
        total_summaries = (("Avg b fat", "b_quan_fat / b_quan"),)

        def get_prepopulation_extra_data(self, request, obj, entity_ids):
            # Extra initial data for new rows: {entity_pk: {field: value}}
            return {pk: {"b_price": 10} for pk in entity_ids}


    class MilkJournalAdmin(HeaderLookupAdminMixin, admin.ModelAdmin):
        inlines = [MilkJournalItemInline]
        header_lookup_fields = ("doc_date", "shift")

Behaviour
---------

* **Add view**: one row per entity of ``get_prepopulation_queryset(request, obj)``.
* **Change view**: saved rows, plus rows for entities that don't have one yet.
* **Locked sheet** (``lock_prepopulated_rows = True``): ``min_num = max_num = rows``,
  so Django's inline JS hides "Add another" and the delete links.
* **Read-only entity** (``prepopulation_readonly = True``): the entity is rendered
  as text plus a hidden input, without a ``<select>`` per row.
* **Saving**: every posted row is saved, including untouched ones (the entity is
  posted without initial data). Journals rely on this, e.g. an untouched employee
  row still records a normal work day.
* **Computed fields** are rendered disabled, so posted values are ignored. The
  model must compute them in ``save()``.
* **Keyboard**: Enter moves to the next editable input (``enter_as_tab``), and
  focusing an input selects its value so typing replaces it.
* JS hook: the inline group dispatches ``erp:totals`` (``detail.totals`` and
  ``detail.summaries``) after each recalculation.

Expressions accept field names of the same row, numbers, ``+ - * /`` and
parentheses. They are tokenised, never ``eval``-ed as free text.

Dynamic entities
----------------

Override ``get_prepopulation_queryset(request, obj)``. On the add view, ``obj``
is ``None`` and header values can be read from ``request.GET``. Combine this with
``HeaderLookupAdminMixin.reload_add_on_header_change = True``: once the header is
chosen, the add page reloads with the header values as GET initial data.

Header lookup
-------------

``HeaderLookupAdminMixin`` adds a ``header-lookup/`` endpoint and htmx attributes
on ``header_lookup_fields``. When those fields identify an existing document,
the browser is redirected to it (``HX-Redirect``). htmx is shipped in
``erp_framework/vendor/htmx``.

Migrating from ``PrepopulatedAdmin``
------------------------------------

``PrepopulatedAdmin`` / ``RaPrePopulatedAdmin`` are deprecated. They override
Django's private ``_create_formsets``, which loses Django's handling of
view-only inlines.

=====================================================  ==========================================
Old (on the ModelAdmin)                                New (on the inline)
=====================================================  ==========================================
``prepopulation_fields = {Inline: "client"}``          ``prepopulation_field = "client"``
``prepopulation_querysets = {Inline: qs}``             ``prepopulation_queryset = qs``
``get_prepopulation_queryset(inline, ...)``            ``get_prepopulation_queryset(request, obj)``
``get_formset_initial`` + ``super()`` + enrich         ``get_prepopulation_extra_data(...)``
=====================================================  ==========================================

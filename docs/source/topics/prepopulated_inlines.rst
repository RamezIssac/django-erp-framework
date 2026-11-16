Prepopulated inlines (data-entry sheets)
=======================================

Daily journals often need *one inline row per entity*: one row per product on
a stock-count sheet, one row per employee on a timesheet, one row per account
on a budget. ``erp_framework.admin.prepopulated`` provides this on the **inline**,
using public Django admin hooks only.

.. code-block:: python

    from django.contrib import admin
    from erp_framework.admin.prepopulated import HeaderLookupAdminMixin, PrepopulatedInlineMixin


    class StockCountLineInline(PrepopulatedInlineMixin, admin.TabularInline):
        model = StockCountLine
        extra = 0
        can_delete = False

        prepopulation_field = "product"                       # FK on the inline model
        prepopulation_queryset = Product.objects.filter(active=True).order_by("code")

        # Display-only, computed live in the browser (the model computes them on save)
        computed_fields = {
            "value": "quantity * unit_price",
        }
        # Sticky totals bar: field names, or (key, label, "row expression");
        # label=None keeps a helper sum hidden.
        total_fields = ("quantity", "value", ("total_weight", None, "quantity * unit_weight"))
        total_summaries = (("Avg price", "value / quantity"),)

        def get_prepopulation_extra_data(self, request, obj, entity_ids):
            # Extra initial data for new rows: {entity_pk: {field: value}}
            return {pk: {"unit_price": 10} for pk in entity_ids}


    class StockCountAdmin(HeaderLookupAdminMixin, admin.ModelAdmin):
        inlines = [StockCountLineInline]
        header_lookup_fields = ("doc_date", "warehouse")

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
* **Saving never duplicates rows**: if a *new* row's entity is already saved for
  the document (autosave, another tab, a page opened earlier), the row is bound to
  that item and updated.
* **Computed fields** and **totals**: see below; totals are updated incrementally.
* JS hooks: the inline group dispatches ``erp:totals`` (``detail.totals`` and
  ``detail.summaries``) after each recalculation, and ``erp:saved``
  (``detail.row``, ``detail.response``) after each autosave.

Expressions accept field names of the same row, numbers, ``+ - * /`` and
parentheses. They are tokenised, never ``eval``-ed as free text.

Spreadsheet keyboard
--------------------

Focusing a cell selects its value, so typing replaces it.

=======================  =====================================================
Key                      Action
=======================  =====================================================
Up / Down                same column, previous / next row
Ctrl+Up / Ctrl+Down      first / last row
PageUp / PageDown        10 rows up / down
Left / Right             previous / next cell (visual order, right-to-left aware)
Home / End               first / last cell of the row
Enter / Shift+Enter      next / previous cell, wrapping to the adjacent row
                         (``enter_as_tab = True``)
F2 or double-click       edit inside the cell: Left / Right move the caret
Escape                   revert the cell to its value when it got focus
=======================  =====================================================

With ``numeric_text_inputs = True`` (default), number inputs are rendered as
``inputmode="decimal"`` text inputs, so arrow keys and the mouse wheel never
change a value. The header row and the entity column stay visible while
scrolling.

Fast rendering
--------------

With ``fast_rendering = True`` (default, locked sheets only), the inline uses a
lean template whose rows are built in Python by the ``erp_grid_rows`` template
tag instead of one Django widget template per input. Plain ``<input>`` widgets
are rendered with the same markup as Django's templates; other widgets fall back
to normal rendering. On a 526-row x 15-column sheet this takes the page from
~1.1 s / 6.4 MB to ~0.3 s / 1.6 MB. Set ``fast_rendering = False`` to keep the
theme's tabular template.

Autosave
--------

Set ``autosave = True`` on the inline and add ``GridAutosaveAdminMixin`` to the
parent ``ModelAdmin``:

.. code-block:: python

    from erp_framework.admin.prepopulated import (
        GridAutosaveAdminMixin, HeaderLookupAdminMixin, PrepopulatedInlineMixin,
    )


    class StockCountLineInline(PrepopulatedInlineMixin, admin.TabularInline):
        ...
        autosave = True


    class StockCountAdmin(GridAutosaveAdminMixin, HeaderLookupAdminMixin, admin.ModelAdmin):
        inlines = [StockCountLineInline]
        header_lookup_fields = ("doc_date", "warehouse")

When a cell is committed (blur, Enter, arrow keys), its row is POSTed with htmx
to ``grid-autosave/``:

* The row is matched to its saved item by (document, entity), so it is created
  once and updated afterwards.
* It is validated and saved through a one-form formset and the admin's own
  ``save_formset()``, so the admin's save hooks run as on a full save. Errors
  come back per field and are shown on the cell.
* On the add page, the first save creates the document from the main form (or
  continues on the existing one if its ``header_lookup_fields`` already exist),
  and the page switches to the change URL.
* Saves are queued one at a time. Each row shows its state (pending, saving,
  saved, error), and a status line in the totals bar summarises it. The page
  "Save" button waits for the queue, and leaving the page with unsaved rows
  asks for confirmation.

Header changes (e.g. the date) are still saved by the page "Save" button only.
Autosave doesn't write an admin log entry per cell.

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

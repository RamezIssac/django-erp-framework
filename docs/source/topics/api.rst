JSON API (django-admin-api-mcp)
===============================

The ERP admin can also be used as a JSON API through `django-admin-api-mcp` (package ``admin_api``).
There is no second admin class to write. The same ``EntityAdmin`` / ``TransactionAdmin``
drives the HTML admin and the API, and it differs only where you write an ``api_`` twin.

Setup
-----

.. code-block:: python

    # settings.py
    INSTALLED_APPS += ["admin_api"]
    MIDDLEWARE += ["admin_api.middleware.ApiRequestMiddleware"]

    # urls.py
    from erp_framework.api import erp_api_site

    urlpatterns += [path("api/", erp_api_site.urls)]

Endpoints
---------

==========================================================  =====================================================
``GET /api/v1/``                                            apps and models you can use, with your permissions
``GET /api/v1/<app>/<model>/``                              changelist: filters, ``?q=`` search, ``?o=`` ordering, ``?p=`` page
``GET /api/v1/<app>/<model>/schema/``                       columns, filters, form fields, inlines, actions
``POST /api/v1/<app>/<model>/``                             create (with inline rows)
``GET|PATCH|PUT|DELETE /api/v1/<app>/<model>/<pk>/``        detail / update / delete
``GET /api/v1/<app>/<model>/<pk>/delete-preview/``          what a delete would remove
``POST /api/v1/<app>/<model>/actions/<name>/``              run an admin action on ``{"pks": [...]}``
==========================================================  =====================================================

Writes and ERP hooks
--------------------

A JSON write is translated into the change form's POST data and handed to
``EntityAdmin.process_changeform(request, obj, change)``. That is the same method the HTML change
form uses, so ``whole_changeform_validation``, ``pre_save``, ``post_save``, ``changeform_saved``,
``save_formset`` (copying header fields to the item lines), LogEntry and reversion all behave
identically.

.. code-block:: json

    POST /api/v1/store/sales/
    {
      "slug": "INV-1", "date": "2025-04-01T09:00:00+00:00", "client": 1, "store": 1,
      "inlines": {"items": [{"product": 1, "quantity": "2", "price": "50"}]}
    }

In ``PATCH``, inline rows with ``pk`` are updated (``"_delete": true`` deletes them), and rows
without ``pk`` are created.

API-specific behaviour: ``api_`` twins
--------------------------------------

.. code-block:: python

    class SalesAdmin(TransactionAdmin):
        api_list_display = ["slug", "date", "client", "value"]      # no HTML columns
        api_detail_fields = ["slug", "date", "client", "notes", "value"]

        def get_api_queryset(self, request):
            return super().get_queryset(request).select_related("client")

        def get_readonly_fields(self, request, obj=None):
            if request.is_api:
                return [*super().get_readonly_fields(request, obj), "slug"]
            return super().get_readonly_fields(request, obj)

The lookup order is ``get_api_X(request)`` → ``api_X`` → ``get_X(request)`` → ``X``. To hide an
admin from the API, set ``api_enabled = False``.

Authentication
--------------

The API accepts the admin session (with CSRF) or a personal access token
(``Authorization: Bearer aapi_…``). Tokens are created in the admin under "API tokens", or with
``manage.py create_api_token <username>``. A token has exactly its user's permissions.

MCP: AI agents
--------------

The same admins can be used by AI agents (Claude Code, Claude Desktop, any MCP client) through
django-admin-api-mcp, with the same permissions, ``whole_changeform_validation``,
``pre_save``/``post_save`` hooks, LogEntry and reversion.

.. code-block:: bash

    pip install django-admin-api-mcp

.. code-block:: python

    # urls.py
    from erp_framework.api import erp_mcp_site

    urlpatterns += [path("mcp/", erp_mcp_site.urls)]   # Streamable HTTP

.. code-block:: bash

    # a token for the agent, narrowed with scopes
    python manage.py create_api_token alice --kind mcp --name claude --scope "store.*:view"
    # local agent over stdio
    claude mcp add erp -e ADMIN_API_TOKEN=aapi_... -- python manage.py mcp_serve

Tools: ``list_models``, ``describe_model``, ``list_objects``, ``get_object``,
``create_object``/``update_object`` (with ``dry_run``), ``delete_object`` (preview unless
``confirm``), ``run_action``, ``resolve_entities``. ``EntityAdmin`` list rows carry the plain
``name`` column in place of the HTML title column. Give the agent context with
``mcp_description = "..."`` on an admin; hide an admin from MCP only with ``mcp_enabled = False``.

Reports over MCP
~~~~~~~~~~~~~~~~

``erp_mcp_site`` also publishes the registered reports as read-only tools, through
``erp_framework.reporting.mcp.ReportToolsMixin``. These tools need django-slick-reporting's headless
runner (``ReportViewBase.run`` with ``max_rows``), ``slick_reporting.helpers.compact_response`` and
``slick_reporting.dynamic_report``. With a django-slick-reporting that lacks them, ``erp_mcp_site``
publishes the admin tools only.

- ``list_reports``: the reports the user may run. Each entry carries ``report`` (the code,
  ``<base_model>.<report_slug>``), ``question`` (the short catalog question), ``params`` (each parameter
  that picks records mapped to its model, e.g. ``{"client_id": "store.client"}``) and ``order_by``
  (``{key: label}`` of the computed columns ``run_report`` can sort by, e.g.
  ``{"__balance__": "Closing Total"}``; empty for list reports). The ``fields`` argument adds any of:
  ``title``, ``description``, ``base_model`` and ``base_model_name`` (the verbose name), ``kind``
  (``group``, ``series``, ``crosstab`` or ``list``), ``date_filter``, ``balance`` (true when a column adds
  everything before ``start_date``, such as ``__balance__``) and ``columns`` (the column labels). An
  unknown field is refused with a ``help`` line naming the accepted ones.
  A parameter whose model is not exposed through MCP, or is in ``excluded_models``, is left out of ``params`` and ``params_schema``.
- ``describe_report``: the report's parameters as JSON Schema (``params_schema``), its columns,
  group by, date field, time series pattern and crosstab field, with ``base_model_name`` and
  ``report_model_name`` next to the model paths. Foreign-key parameters take
  IDs of the model named in ``x-related-model``; the server instructions point the agent to
  ``resolve_entities`` with ``models`` set to that value to turn a typed name into IDs.
  The instructions also ask the agent to name reports by title and records by label. Refusals and field
  errors are worded with verbose names and carry a plain ``detail``, without model paths.
- ``run_report``: runs the report through django-slick-reporting's headless runner and returns
  ``columns``, positional ``rows``, ``totals`` over all rows, ``row_count``, ``truncated`` and
  ``date_window``. ``max_rows`` defaults to 50 (``report_max_rows``) and is capped at 1000
  (``report_max_rows_cap``). A single ID for a parameter that
  takes a list of IDs is read as a one-item list. ``order_by`` takes one of the report's ``order_by``
  keys, ``-key`` for highest first, and goes to slick as ``default_order_by``; with ``max_rows`` it
  gives a top N, and ``totals`` still cover every row. Another key, or any key on a list report, is
  refused with the keys it accepts. A foreign-key parameter
  naming a row that the related model admin's ``get_queryset(request)`` hides is rejected.
  See `Row policy and help lines`_ for ``help``, ``total_columns`` and ``summary_report``.
- ``list_dynamic_report_models``: the models and fields a dynamic report spec may use, each with its
  ``verbose_name``, plus the spec grammar: ``spec_schema``
  (``slick_reporting.dynamic_report.DYNAMIC_REPORT_SPEC_SCHEMA``), ``spec_guide`` and ``spec_example``.
- ``run_dynamic_report``: builds and runs an ad-hoc report from django-slick-reporting's JSON
  report spec and returns the
  same shape as ``run_report``. The spec may only read the MCP-exposed models the user may view,
  never the user model nor the site's ``excluded_models`` (``get_dynamic_report_models(request)``).
  Rows follow each model admin's ``get_queryset(request)``, and field paths may only use the fields
  the admin shows (change form, readonly and ``list_display`` fields and the primary key, minus
  ``get_exclude(request)``). On a multi-table inheritance child the parent's primary key (``id``)
  counts as the primary key, so ``{"method": "Count", "field": "id"}`` counts its rows.
  Its description, built per request by ``get_dynamic_report_catalog(request, room)``, carries the spec
  grammar (``spec_guide``: kinds, aggregation methods, time series patterns), ``spec_example`` and one
  line per model the user may read: ``label (name): field, number#, date@, relation>label`` when that
  fits in ``report_tool_description_max_chars``, else only the number, date and relation fields, else
  the labels alone, else the agent calls ``list_dynamic_report_models``.

A report is listed and runnable when ``is_report_exposed(report)`` allows it,
``report_access_function(request, "view", report)`` passes and the token scopes allow ``view`` on its
base model. By default ``is_report_exposed`` keeps a report whose base model's admin is exposed through
MCP (``is_exposed``), and a report without a base model.

The server instructions route questions to reports: answer totals and balances with a report, resolve
typed names with ``resolve_entities``, then call ``run_report``. ``run_report``'s description, built per
request by ``get_report_catalog(request, room)``, ends with a catalog: one line per report the user may
run, when there are at most ``report_catalog_max`` (40) of them. The whole description stays within
``report_tool_description_max_chars`` (4096). Each line is enough for a plain run:
``code: description | params ... | order_by key=label | balance`` when that fits, else
``code: question | params ... | order_by keys`` with the short question, else
``code | params ... | order_by keys``, else the code alone, else the catalog is left out and the agent
calls ``list_reports``. The description says the listed params and ``order_by`` keys are complete and
optional, with their defaults, and to call ``describe_report`` only for a parameter a line does not list.

Claude Code keeps 4,096 characters of server instructions and of each tool description (16,384 once
the tool is loaded through tool search). The instructions keep only the routing rules.

Narrow the reports, or change the row limits, in a subclass:

.. code-block:: python

    from admin_api.mcp import AdminMcpSite
    from erp_framework.reporting.mcp import ReportToolsMixin

    class MyMcpSite(ReportToolsMixin, AdminMcpSite):
        report_max_rows = 100
        report_max_rows_cap = 500

        def is_report_exposed(self, report_class):
            return super().is_report_exposed(report_class) and report_class.get_base_model_name() != "payroll"

Row policy and help lines
~~~~~~~~~~~~~~~~~~~~~~~~~

A report class may declare two attributes for ``run_report``:

.. code-block:: python

    class ClientStatement(ListReportView):
        columns = ["slug", "date", "product__name", "quantity", "price", "value"]
        total_columns = ["value"]
        summary_report = "client.balances"  # or the report class

- ``total_columns`` (django-slick-reporting): the columns ``totals`` covers, over every row, on top of
  slick's summable computed columns. Without it, a list report returns ``totals: {}``.
- ``summary_report``: the code (or class) of the report that aggregates this report's rows. ``help``
  names it when the user may run it.

``run_report`` passes ``max_rows`` to slick's ``run()``: a list report builds at most that many rows and
counts and totals all rows in the database.
A list report that declares ``total_columns`` and is run without ``max_rows`` over more than
``report_max_rows`` rows returns its ``totals`` and its first ``report_summary_rows`` (10) rows.
An explicit ``max_rows`` returns that many rows, up to the cap.

``run_report`` adds ``help`` (a list of lines) when no row matches or when the default ``max_rows``
cut the rows. On a cut, the lines name ``order_by`` and ``max_rows`` for a top N (reports with
``order_by`` keys), a ``params`` filter for one record, the ``summary_report`` and ``max_rows`` for more
rows. With no rows, they name the date window to widen and the record filters to drop. Errors carry
``help`` too: the closest report code for an unknown one, and the corrected ``run_report`` call for an
unknown parameter, a bad ID or an unknown ``order_by`` key.

``get_report_question(report_class, request)`` returns ``report_question`` (5 to 8 words, for the
catalog), else the title. ``get_report_description(report_class, request)`` returns
``report_description``, else the class docstring, else the title. Override either to give the agent
more context.

**Dry runs and side effects.** ``dry_run`` runs the whole changeform pipeline, including
``pre_save``, ``post_save`` and the ``changeform_saved`` signal, then rolls the database back.
Side effects outside the database (e-mails, queued jobs) still happen unless you guard them:
use ``transaction.on_commit`` (discarded by a dry run), or check ``request.is_dry_run``. The
``changeform_saved`` signal now passes ``request`` for this purpose:

.. code-block:: python

    @receiver(changeform_saved)
    def notify(sender, instance, created, request=None, **kwargs):
        if request is not None and request.is_dry_run:
            return
        transaction.on_commit(lambda: send_invoice_mail(instance))


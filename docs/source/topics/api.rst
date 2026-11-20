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
``confirm``), ``run_action``. Give the agent context with ``mcp_description = "..."`` on an
admin; hide an admin from MCP only with ``mcp_enabled = False``.

Reports over MCP
~~~~~~~~~~~~~~~~

``erp_mcp_site`` also publishes the registered reports as read-only tools, through
``erp_framework.reporting.mcp.ReportToolsMixin``:

- ``list_reports``: the reports the user may run, with code (``<base_model>.<report_slug>``),
  title, description, base model, kind (``group``, ``series``, ``crosstab`` or ``list``) and
  whether it filters by date.
- ``describe_report``: the report's parameters as JSON Schema (``params_schema``), its columns,
  group by, date field, time series pattern and crosstab field. Foreign-key parameters take
  primary keys of the model named in ``x-related-model``.
- ``run_report``: runs the report through django-slick-reporting's headless runner and returns
  ``columns``, positional ``rows``, ``totals`` over all rows, ``row_count``, ``truncated`` and
  ``date_window``. ``max_rows`` defaults to 200 and is capped at 1000.
- ``list_dynamic_report_models``: the models and fields a dynamic report spec may use.
- ``run_dynamic_report``: builds and runs an ad-hoc report from django-slick-reporting's JSON
  report spec (``slick_reporting.dynamic_report.DYNAMIC_REPORT_SPEC_SCHEMA``) and returns the
  same shape as ``run_report``. The spec may only read the MCP-exposed models the user may view,
  never the user model (``get_dynamic_report_models`` sets the list).

A report is listed and runnable when ``report_access_function(request, "view", report)`` passes
and the token scopes allow ``view`` on its base model. Every registered report is exposed by
default. Narrow it, or change the row limits, in a subclass:

.. code-block:: python

    from admin_api.mcp import AdminMcpSite
    from erp_framework.reporting.mcp import ReportToolsMixin

    class MyMcpSite(ReportToolsMixin, AdminMcpSite):
        report_max_rows = 100
        report_max_rows_cap = 500

        def is_report_exposed(self, report_class):
            return report_class.get_base_model_name() != "payroll"

``get_report_description(report_class, request)`` returns ``report_description``, else the class
docstring, else the title. Override it to give the agent more context.

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


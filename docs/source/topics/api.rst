JSON API (django-admin-api)
===========================

The ERP admin can also be used as a JSON API through `django-admin-api` (package ``admin_api``).
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
django-admin-api's MCP add-on, with the same permissions, ``whole_changeform_validation``,
``pre_save``/``post_save`` hooks, LogEntry and reversion.

.. code-block:: bash

    pip install "django-admin-api[mcp]"

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


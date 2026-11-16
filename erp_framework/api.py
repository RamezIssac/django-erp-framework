"""
Optional JSON API over the ERP admin site, powered by django-admin-api (``admin_api``).

Every admin registered on ``erp_admin_site`` is exposed (``api_enabled = False`` hides one),
with the same permissions, querysets, forms, inlines and actions as the HTML admin. Writes go
through :meth:`erp_framework.admin.admin.EntityAdmin.process_changeform`, so
``whole_changeform_validation``, ``pre_save``, ``post_save``, the ``changeform_saved`` signal,
LogEntry and reversion all run exactly as they do for the HTML change form.

Setup::

    # settings.py
    INSTALLED_APPS += ["admin_api"]
    MIDDLEWARE += ["admin_api.middleware.ApiRequestMiddleware"]

    # urls.py
    from erp_framework.api import erp_api_site

    urlpatterns += [path("api/", erp_api_site.urls)]   # -> /api/v1/<app>/<model>/

MCP (AI agents), with the same permissions and hooks. Needs ``django-admin-api[mcp]`` for the
transports::

    from erp_framework.api import erp_mcp_site

    urlpatterns += [path("mcp/", erp_mcp_site.urls)]   # Streamable HTTP
    # stdio: ADMIN_API_TOKEN=aapi_... python manage.py mcp_serve

This module requires django-admin-api; erp_framework itself does not.
"""

from admin_api import AdminApiSite
from admin_api.mcp import AdminMcpSite

from erp_framework.sites import erp_admin_site


class ERPApiSite(AdminApiSite):
    """Subclass to change site-wide API behaviour (authenticators, page size, exposure)."""


erp_api_site = ERPApiSite(admin_site=erp_admin_site, name="erp_api")


class ERPMcpSite(AdminMcpSite):
    """Subclass to change MCP behaviour (read_only, instructions, exposure)."""


erp_mcp_site = ERPMcpSite(erp_api_site, name="erp_mcp", server_name="erp")

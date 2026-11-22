"""
Optional JSON API over the ERP admin site, powered by django-admin-api-mcp (``admin_api``).

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

MCP (AI agents), with the same permissions and hooks. Needs ``django-admin-api-mcp`` (MCP is part of it) for the
transports::

    from erp_framework.api import erp_mcp_site

    urlpatterns += [path("mcp/", erp_mcp_site.urls)]   # Streamable HTTP
    # stdio: ADMIN_API_TOKEN=aapi_... python manage.py mcp_serve

The MCP site also publishes the reports as read-only tools; see :mod:`erp_framework.reporting.mcp`.

This module requires django-admin-api-mcp; erp_framework itself does not.
"""

from importlib.util import find_spec

from admin_api import AdminApiSite
from admin_api.mcp import AdminMcpSite
from slick_reporting import helpers as slick_helpers
from slick_reporting.views import ReportViewBase

from erp_framework.sites import erp_admin_site

HAS_REPORT_TOOLS = (
    hasattr(ReportViewBase, "run_max_rows")
    and hasattr(slick_helpers, "compact_response")
    and find_spec("slick_reporting.dynamic_report") is not None
)
if HAS_REPORT_TOOLS:
    from erp_framework.reporting.mcp import ReportToolsMixin

    MCP_SITE_BASES = (ReportToolsMixin, AdminMcpSite)
else:
    MCP_SITE_BASES = (AdminMcpSite,)


class ERPApiSite(AdminApiSite):
    """Subclass to change site-wide API behaviour (authenticators, page size, exposure)."""


erp_api_site = ERPApiSite(admin_site=erp_admin_site, name="erp_api")


class ERPMcpSite(*MCP_SITE_BASES):
    """Subclass to change MCP behaviour (read_only, instructions, exposure, report exposure)."""


erp_mcp_site = ERPMcpSite(erp_api_site, name="erp_mcp", server_name="erp")

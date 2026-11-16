from django.core.exceptions import ImproperlyConfigured
from django.urls import path

from erp_framework.api import erp_api_site, erp_mcp_site
from erp_framework.sites import erp_admin_site

urlpatterns = [
    path("admin/", erp_admin_site.urls),
    path("api/", erp_api_site.urls),
]

try:  # the MCP transport needs django-admin-api[mcp]
    urlpatterns.append(path("mcp/", erp_mcp_site.urls))
except ImproperlyConfigured:
    pass

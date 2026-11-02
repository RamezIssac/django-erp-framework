from django.urls import path

from admin_api import AdminApiSite
from erp_framework.sites import erp_admin_site

api_site = AdminApiSite(admin_site=erp_admin_site)

urlpatterns = [
    path("admin/", erp_admin_site.urls),
    path("api/", api_site.urls),
]

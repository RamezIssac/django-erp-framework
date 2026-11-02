from django.urls import path

from erp_framework.api import erp_api_site
from erp_framework.sites import erp_admin_site

urlpatterns = [
    path("admin/", erp_admin_site.urls),
    path("api/", erp_api_site.urls),
]

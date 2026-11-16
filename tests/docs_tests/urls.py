from django.urls import include, path

from erp_framework.sites import erp_admin_site

urlpatterns = [
    path("docs/", include("erp_framework.docs.urls")),
    path("admin/", erp_admin_site.urls),
]

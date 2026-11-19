from django.contrib import admin
from django.urls import path

from erp_framework.sites import erp_admin_site

urlpatterns = [
    path("admin/", erp_admin_site.urls),
    path("django-admin/", admin.site.urls),
]

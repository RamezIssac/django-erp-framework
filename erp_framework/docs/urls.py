"""
Includable URLconf for the in-app user guide::

    path("docs/", include("erp_framework.docs.urls")),

Every view is wrapped in ``erp_admin_site.admin_view``, so only logged-in
staff can reach them; per-page permissions are checked on top of that.
"""

from django.urls import path

from erp_framework.sites import erp_admin_site

from . import views

app_name = "erp_docs"

urlpatterns = [
    path("", erp_admin_site.admin_view(views.index), name="index"),
    path(
        "assets/<path:asset_path>",
        erp_admin_site.admin_view(views.asset),
        name="asset",
    ),
    path("<path:page_path>/", erp_admin_site.admin_view(views.page), name="page"),
]

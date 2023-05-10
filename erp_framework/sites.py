from django.utils.functional import LazyObject
from django.utils.module_loading import import_string
from .base import app_settings


class DefaultAdminSite(LazyObject):
    def _setup(self):
        AdminSiteClass = import_string(app_settings.ERP_FRAMEWORK_ADMIN_SITE_CLASS)
        self._wrapped = AdminSiteClass(name=app_settings.RA_ADMIN_SITE_NAME)

    def __repr__(self):
        return repr(self._wrapped)


erp_admin_site = DefaultAdminSite()

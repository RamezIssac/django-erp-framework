from django.conf import settings
from django.urls import get_callable

ERP_FRAMEWORK_SETTINGS = {
    "site_name": "ERP Framework System",
    "site_header": "ERP Framework System",
    "index_title": "Dashboard Home",
    "index_template": "admin/index.html",
    "login_template": "admin/login.html",
    "logout_template": "admin/logout.html",
    "app_index_template": "admin/app_index.html",
    # a function to control be dbfield on all instances, Saves you time to subclass if
    # only you need to add a help text or something
    "admin_default_formfield_for_dbfield": (
        "erp_framework.base.helpers.default_formfield_for_dbfield"
    ),
    "admin_site_class": "erp_framework.admin.admin.ERPFrameworkAdminSite",
    "admin_site_namespace": "erp_framework",
    "enable_delete_all": False,
}

USER_FRAMEWORK_SETTINGS = getattr(settings, "ERP_FRAMEWORK_SETTINGS", {})

ERP_FRAMEWORK_SETTINGS.update(USER_FRAMEWORK_SETTINGS)

"""
UnDocumented
"""

RA_REPORT_LIST_MAP = getattr(settings, "RA_REPORT_LIST_MAP", {})

ERP_FRAMEWORK_THEME = getattr(settings, "ERP_FRAMEWORK_THEME", "admin")

# correct
ERP_ADMIN_SITE_TITLE = ERP_FRAMEWORK_SETTINGS.get("site_name", "ERP Framework System")

ERP_ADMIN_SITE_HEADER = ERP_FRAMEWORK_SETTINGS.get("site_name", "ERP Framework Header")

ERP_ADMIN_INDEX_TITLE = ERP_FRAMEWORK_SETTINGS.get("index_title", "")

ERP_ADMIN_INDEX_TEMPLATE = ERP_FRAMEWORK_SETTINGS.get("index_template", "")

ERP_ADMIN_DEFAULT_FORMFIELD_FOR_DBFIELD_FUNC = ERP_FRAMEWORK_SETTINGS.get(
    "admin_default_formfield_for_dbfield", ""
)

ERP_ADMIN_DEFAULT_FORMFIELD_FOR_DBFIELD_FUNC = get_callable(
    ERP_ADMIN_DEFAULT_FORMFIELD_FOR_DBFIELD_FUNC
)

ERP_FRAMEWORK_ADMIN_SITE_CLASS = ERP_FRAMEWORK_SETTINGS.get(
    "admin_site_class", "erp_framework.admin.admin.ERPFrameworkAdminSite"
)

ERP_FRAMEWORK_SITE_NAME = ERP_FRAMEWORK_SETTINGS.get(
    "admin_site_namespace", "erp_framework"
)

ERP_FRAMEWORK_LOGIN_TEMPLATE = ERP_FRAMEWORK_SETTINGS.get(
    "login_template", "admin/login.html"
)

ERP_FRAMEWORK_APP_INDEX_TEMPLATE = ERP_FRAMEWORK_SETTINGS.get(
    "app_index_template", "admin/app_index.html"
)

ERP_FRAMEWORK_LOGGED_OUT_TEMPLATE = ERP_FRAMEWORK_SETTINGS.get(
    "logout_template", "admin/logout.html"
)

ERP_FRAMEWORK_ENABLE_ADMIN_DELETE_ALL = ERP_FRAMEWORK_SETTINGS.get(
    "enable_delete_all", False
)

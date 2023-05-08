# coding=utf-8
import pytz
from django.conf import settings
from django.urls import get_callable
from django.utils.functional import lazy

# def get_first_of_this_year():
#     d = datetime.datetime.today()
#     return datetime.datetime(d.year, 1, 1, 0, 0, 0, 0, pytz.timezone(settings.TIME_ZONE))
#
#
# def get_end_of_this_year():
#     d = datetime.datetime.today()
#     return datetime.datetime(d.year + 1, 1, 1, 0, 0, 0, 0, pytz.timezone(settings.TIME_ZONE))


import datetime

ERP_FRAMEWORK_SETTINGS = {
    "site_name": "ERP Framework System",
    "site_header": "ERP Framework System",
    "index_title": "Dashboard Home",
    "index_template": "",
    # a function to control be dbfield on all instances, Saves you time to subclass ifonly you need to add a help text or something
    "admin_default_formfield_for_dbfield": "erp_framework.base.helpers.default_formfield_for_dbfield",
}

USER_FRAMEWORK_SETTINGS = getattr(settings, "ERP_FRAMEWORK_SETTINGS", {})

ERP_FRAMEWORK_SETTINGS.update(USER_FRAMEWORK_SETTINGS)

"""
UnDocumented
"""

RA_ENABLE_ADMIN_DELETE_ALL = getattr(settings, "RA_ENABLE_ADMIN_DELETE_ALL", False)

# RA_DEFAULT_FROM_DATETIME = lazy(get_first_of_this_year, datetime.datetime)()
# RA_DEFAULT_TO_DATETIME = lazy(get_end_of_this_year, datetime.datetime)()
# # models


RA_ADMIN_SITE_NAME = getattr(settings, "RA_ADMIN_SITE_NAME", "erp_admin")

RA_REPORT_LIST_MAP = getattr(settings, "RA_REPORT_LIST_MAP", {})

RA_MENU_HIDE_MODELS = getattr(settings, "RA_MENU_HIDE_MODELS", [])
ADMIN_REORDER = getattr(settings, "ADMIN_REORDER", [])

RA_FLOATFORMAT_ARG = getattr(settings, "RA_FLOATFORMAT_ARG", "-2")

# Cache
# =====

RA_CACHE_REPORTS = getattr(settings, "RA_CACHE_REPORTS", True)
RA_CACHE_REPORTS_PER_USER = getattr(settings, "RA_CACHE_REPORTS_PER_USER", True)

# Style
RA_THEME = getattr(settings, "RA_THEME", "admin")

# Admin Looks
from django.utils.translation import gettext_lazy as _

RA_ADMIN_APP_INDEX_TEMPLATE = getattr(
    settings, "RA_ADMIN_APP_INDEX_PAGE", f"{RA_THEME}/app_index.html"
)
RA_ADMIN_LOGIN_TEMPLATE = getattr(
    settings, "RA_ADMIN_LOGIN_TEMPLATE", f"{RA_THEME}/login.html"
)
RA_ADMIN_LOGGED_OUT_TEMPLATE = getattr(
    settings, "RA_ADMIN_LOGIN_TEMPLATE", f"{RA_THEME}/logged_out.html"
)

RA_ADMIN_SITE_CLASS = getattr(
    settings, "RA_ADMIN_SITE_CLASS", "erp_framework.admin.admin.RaAdminSite"
)
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

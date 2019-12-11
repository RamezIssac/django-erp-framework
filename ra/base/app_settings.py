# coding=utf-8
import pytz
from django.conf import settings
from django.urls import get_callable
from django.utils.functional import lazy


def get_first_of_this_year():
    d = datetime.datetime.today()
    return datetime.datetime(d.year, 1, 1, 0, 0, 0, 0, pytz.timezone(settings.TIME_ZONE))


import datetime

"""
Documented
"""
# a function to control be dbfield on all instances, Saves you time to subclass ifonly you need to add a help text or something
RA_FORMFIELD_FOR_DBFIELD_FUNC = getattr(settings, 'RA_FORMFIELD_FOR_DBFIELD_FUNC',
                                        'ra.base.helpers.default_formfield_for_dbfield')
RA_FORMFIELD_FOR_DBFIELD_FUNC = get_callable(RA_FORMFIELD_FOR_DBFIELD_FUNC)

# Navigation class
RA_NAVIGATION_CLASS = getattr(settings, 'RA_NAVIGATION_CLASS', 'ra.utils.navigation.RaSuitMenu')

"""
UnDocumented
"""

RA_ENABLE_ADMIN_DELETE_ALL = getattr(settings, 'RA_ENABLE_ADMIN_DELETE_ALL', False)

RA_AUTOCOMPLETE_ALIASES = getattr(settings, 'RA_AUTOCOMPLETE_ALIASES', {})

# Date related settings
RA_DATETIME_DISPLAY_FORMAT = getattr(settings, 'RA_DATETIME_DISPLAY_FORMAT', '%Y/%m/%d %H:%M')
RA_DATETIME_SAVE_FORMAT = getattr(settings, 'RA_DATETIME_SAVE_FORMAT', '%Y-%m-%d %H:%M:%S %z')

DEFAULT_FROM_DATE_TIME = lazy(get_first_of_this_year, datetime.datetime)()

# models

RA_BASEINFO_MODEL = getattr(settings, 'RA_BASEINFO_MODEL', 'ra.base.models.BaseInfo')
RA_BASEMOVEMENTINFO_MODEL = getattr(settings, 'RA_BASEINFO_MODEL', 'ra.abstract_models.BaseMovementInfo')
RA_QUANVALUEMOVEMENTITEM_MODEL = getattr(settings, 'RA_QUANVALUEMOVEMENTITEM_MODEL',
                                         'ra.base.models.QuanValueMovementItem')

_default_print = {
    'left_header': r'Company name \\ Company address \\ Company Telephone \\',
    'center_header': '',
    'right_header': '',
    'center_footer': r'',
    'left_footer': '',
    'right_footer': r'\thepage\ / \pageref{LastPage}',
    'pre_table_template': 'ra/tex/pre_table_typed_report.html',
    'documentclass': 'article',
    'documentsize': 'a4paper',
    'document_orientation': 'portrait',
    'pre_headers': '',
    'provide_total': 'auto',
    'provide_total_on': False,
    'hide_all_fk_slugs': False,
    'enable_smart_date': True,
    'col_sizes': {},
    'time_series_col_size': 'C{1cm}|',
    'extra_row_separator': r' \hline',
}
# _default_print_bidi = {
#     'right_header': r'Company name \\ Company address \\ Company Telephone \\',
#     'left_header': '',
#
# }


_user_print_settings = getattr(settings, 'RA_PRINT_SETTINGS', {})
_default_print.update(_user_print_settings)
RA_PRINT_SETTINGS = _default_print
_default_print_bidi = {
    'right_header': RA_PRINT_SETTINGS['left_header'],
    'left_header': ''
}
_user_print_settings = getattr(settings, 'RA_PRINT_SETTINGS_RTL', {})
_default_print_bidi.update(_user_print_settings)
RA_PRINT_SETTINGS_RTL = _default_print_bidi

RA_APP_ICONS = getattr(settings, 'RA_APP_ICONS', {})

RA_ADMIN_SITE_NAME = getattr(settings, 'RA_ADMIN_SITE_NAME', 'ra_admin')

RA_REPORT_LIST_MAP = getattr(settings, 'RA_REPORT_LIST_MAP', {})

RA_MENU_HIDE_MODELS = getattr(settings, 'RA_MENU_HIDE_MODELS', [])
ADMIN_REORDER = getattr(settings, 'ADMIN_REORDER', [])

RA_FLOATFORMAT_ARG = getattr(settings, 'RA_FLOATFORMAT_ARG', '-2')

# Cache
# =====

RA_CACHE_REPORTS = getattr(settings, 'RA_CACHE_REPORTS', True)
RA_CACHE_REPORTS_PER_USER = getattr(settings, 'RA_CACHE_REPORTS_PER_USER', False)  # todo fix as it raise error

# Style
RA_THEME = getattr(settings, 'RA_THEME', 'adminlte')

# Admin Looks
from django.utils.translation import ugettext_lazy as _

RA_SITE_TITLE = getattr(settings, '', _('Ra ERP'))

RA_ADMIN_INDEX_PAGE = getattr(settings, 'RA_ADMIN_INDEX_PAGE', f'{RA_THEME}/index.html')
RA_ADMIN_APP_INDEX_PAGE = getattr(settings, 'RA_ADMIN_APP_INDEX_PAGE', 'ra/admin/app_index.html')
RA_ADMIN_LOGIN_PAGE = getattr(settings, 'RA_ADMIN_LOGIN_PAGE', 'ra/admin/login.html')
RA_ADMIN_PASSWORD_PAGE = getattr(settings, 'RA_ADMIN_PASSWORD_PAGE', 'ra/registration/password_change_form.html')
RA_ADMIN_SITE_CLASS = getattr(settings, 'RA_ADMIN_SITE_CLASS', 'ra.admin.admin.RaAdminSite')

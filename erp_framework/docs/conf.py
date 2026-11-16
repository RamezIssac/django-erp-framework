"""
Settings access for the ``erp_docs`` app.

All settings are read lazily from ``django.conf.settings`` so tests can use
``override_settings`` and projects can change them without touching the
framework.

``ERP_DOCS_TITLE``
    Guide title shown in the chrome. Default: ``"User guide"``.

``ERP_DOCS_SOURCE_DIRS``
    Ordered list of extra directories holding Markdown pages, appended after
    the auto-discovered ``docs/`` directories of installed apps. When two
    sources provide the same page, the *later* directory wins, so a client
    project lists its own guide directory last and shadows module pages.

``ERP_DOCS_AUTODISCOVER``
    Default ``True``. When enabled, every installed app that ships a
    ``docs/`` directory in its package contributes pages.

``ERP_DOCS_ACCESS_FUNCTION``
    Dotted path to a callable ``(request) -> bool`` controlling access to the
    whole guide (mirrors ``report_access_function``). Default:
    ``erp_framework.docs.helpers.user_can_access_docs`` (active staff).
"""

from django.conf import settings
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _

DEFAULT_ACCESS_FUNCTION = "erp_framework.docs.helpers.user_can_access_docs"


def get_title():
    return getattr(settings, "ERP_DOCS_TITLE", _("User guide"))


def get_source_dirs():
    return getattr(settings, "ERP_DOCS_SOURCE_DIRS", [])


def autodiscover_enabled():
    return getattr(settings, "ERP_DOCS_AUTODISCOVER", True)


def get_access_function():
    path = getattr(settings, "ERP_DOCS_ACCESS_FUNCTION", DEFAULT_ACCESS_FUNCTION)
    return import_string(path)

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ERPDocsConfig(AppConfig):
    """
    In-app user documentation: renders Markdown guide pages per request,
    in a standalone full-page layout, for logged-in staff.

    Add ``"erp_framework.docs"`` to ``INSTALLED_APPS`` and include
    ``erp_framework.docs.urls`` in the project URLconf, e.g.::

        path("docs/", include("erp_framework.docs.urls")),
    """

    name = "erp_framework.docs"
    label = "erp_docs"
    verbose_name = _("User guide")

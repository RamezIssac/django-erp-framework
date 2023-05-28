from django.apps import AppConfig

from django.utils.translation import gettext_lazy as _


class ERPFrameworkConfig(AppConfig):
    name = "erp_framework"
    verbose_name = _("ERP Framework")

    def ready(self):
        super().ready()
        from . import checks  # noqa

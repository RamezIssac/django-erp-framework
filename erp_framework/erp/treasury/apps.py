from django import apps
from django.utils.translation import gettext_lazy as _


class TreasuryConfig(apps.AppConfig):
    name = "erp_framework.erp.treasury"
    verbose_name = _("Treasury")

    def ready(self):
        super(TreasuryConfig, self).ready()

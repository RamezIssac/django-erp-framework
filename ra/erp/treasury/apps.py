from django import apps
from django.utils.translation import ugettext_lazy as _


class TreasuryConfig(apps.AppConfig):
    name = 'ra.erp.treasury'
    verbose_name = _("Treasury")

    def ready(self):
        super(TreasuryConfig, self).ready()

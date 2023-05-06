from django import apps
from django.utils.translation import gettext_lazy as _


class ExpenseConfig(apps.AppConfig):
    name = 'erp_framework.erp.expense'
    verbose_name = _("Expense")

    def ready(self):
        super(ExpenseConfig, self).ready()
        from . import reports


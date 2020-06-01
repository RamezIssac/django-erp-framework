from django import apps
from django.utils.translation import ugettext_lazy as _


class ExpenseConfig(apps.AppConfig):
    name = 'ra.erp.expense'
    verbose_name = _("Expense")

    def ready(self):
        super(ExpenseConfig, self).ready()
        from . import reports


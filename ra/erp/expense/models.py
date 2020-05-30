from ra.base.models import EntityModel
from django.utils.translation import ugettext_lazy as _


class Expense(EntityModel):
    class Meta:
        verbose_name = _('Expense')
        verbose_name_plural = _('Expenses')

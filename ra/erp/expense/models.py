from ra.base.models import EntityModel, TransactionItemModel, TransactionModel
from django.utils.translation import ugettext_lazy as _
from django.db import models


class Expense(EntityModel):
    class Meta:
        verbose_name = _('Expense')
        verbose_name_plural = _('Expenses')


class ExpenseTransaction(TransactionModel):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, verbose_name=_('Expense'))
    treasury = models.ForeignKey('treasury.Treasury', on_delete=models.CASCADE, verbose_name=_('Treasury'))


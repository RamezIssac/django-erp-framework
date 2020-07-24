from ra.admin.admin import EntityAdmin, TransactionAdmin, ra_admin_site
from .models import Expense, ExpenseTransaction


class ExpenseAdmin(EntityAdmin):
    pass


class ExpenseTransactionAdmin(TransactionAdmin):
    fields = ('slug', 'doc_date', 'treasury', 'expense', 'value', 'notes')


ra_admin_site.register(Expense, ExpenseAdmin)
ra_admin_site.register(ExpenseTransaction, ExpenseTransactionAdmin)

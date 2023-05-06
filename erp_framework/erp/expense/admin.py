from erp_framework.admin.admin import EntityAdmin, TransactionAdmin, erp_admin_site
from .models import Expense, ExpenseTransaction


class ExpenseAdmin(EntityAdmin):
    pass


class ExpenseTransactionAdmin(TransactionAdmin):
    fields = ("slug", "date", "treasury", "expense", "value", "notes")


erp_admin_site.register(Expense, ExpenseAdmin)
erp_admin_site.register(ExpenseTransaction, ExpenseTransactionAdmin)

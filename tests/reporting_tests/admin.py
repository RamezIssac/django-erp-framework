from ra.admin.admin import EntityAdmin, ra_admin_site, TransactionAdmin, TransactionItemAdmin, RaPrePopulatedAdmin
from .models import Client, Product, SimpleSales, Invoice, InvoiceLine, JournalItem, Journal


class ClientAdmin(EntityAdmin):
    view_template = 'client_view.html'


class ProductAdmin(EntityAdmin):
    pass


class SimpleSalesAdmin(TransactionAdmin):
    pass


ra_admin_site.register(Client, ClientAdmin)
ra_admin_site.register(Product, ProductAdmin)
ra_admin_site.register(SimpleSales, SimpleSalesAdmin)


class InvoiceLineAdmin(TransactionItemAdmin):
    fields = ['product', 'quantity', 'discount', 'value']
    model = InvoiceLine
    autocomplete_fields = ['product']


class InvoiceAdmin(TransactionAdmin):
    fields = [('slug', 'date'), 'client']
    autocomplete_fields = ['client']
    inlines = [InvoiceLineAdmin]
    copy_to_formset = ['client']

ra_admin_site.register(Invoice, InvoiceAdmin)

class BaseInfoInlineAdmin(TransactionItemAdmin):
    model = JournalItem

#
# class Journal2Admin(RaPrePopulatedAdmin):
#     inlines = [
#         BaseInfoInlineAdmin
#     ]
#     prepopulation_fields = {
#         BaseInfoInlineAdmin: 'client'
#     }
#     prepopulation_querysets = {
#         BaseInfoInlineAdmin: Client.objects.all()
#     }
#
#     def get_prepopulation_queryset(self, inline, inline_queryset, request, obj, change):
#         queryset = self.prepopulation_querysets.get(inline.__class__, None)
#         if queryset:
#             queryset = queryset.filter(criteria=obj.criteria)
#         return queryset
#


class MovementPrepopulatedAdmin(RaPrePopulatedAdmin):
    fields = ('data', 'date')
    date_hierarchy = None
    list_display = []
    inlines = [
        BaseInfoInlineAdmin
    ]
    prepopulation_fields = {
        BaseInfoInlineAdmin: 'client'
    }
    prepopulation_querysets = {
        BaseInfoInlineAdmin: Client.objects.all()
    }


ra_admin_site.register(Journal, MovementPrepopulatedAdmin)

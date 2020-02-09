from ra.admin.admin import RaAdmin, ra_admin_site, RaMovementAdmin, RaMovementInlineAdmin, RaPrePopulatedAdmin
from .models import Client, Product, SimpleSales, Invoice, InvoiceLine, JournalItem, Journal


class ClientAdmin(RaAdmin):
    view_template = 'client_view.html'


class ProductAdmin(RaAdmin):
    pass


class SimpleSalesAdmin(RaMovementAdmin):
    pass


ra_admin_site.register(Client, ClientAdmin)
ra_admin_site.register(Product, ProductAdmin)
ra_admin_site.register(SimpleSales, SimpleSalesAdmin)


class InvoiceLineAdmin(RaMovementInlineAdmin):
    fields = ['product', 'quantity', 'discount', 'value']
    model = InvoiceLine
    autocomplete_fields = ['product']


class InvoiceAdmin(RaMovementAdmin):
    fields = [('slug', 'doc_date'), 'client']
    autocomplete_fields = ['client']
    inlines = [InvoiceLineAdmin]
    copy_to_formset = ['client']

ra_admin_site.register(Invoice, InvoiceAdmin)

class BaseInfoInlineAdmin(RaMovementInlineAdmin):
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
    fields = ('data', 'doc_date')
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

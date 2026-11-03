from erp_framework.sites import erp_admin_site

from erp_framework.admin.admin import (
    EntityAdmin,
    TransactionAdmin,
    TransactionItemAdmin,
)
from erp_framework.admin.prepopulated import (
    HeaderLookupAdminMixin,
    PrepopulatedInlineMixin,
)
from .models import (
    Client,
    Product,
    SimpleSales,
    Invoice,
    InvoiceLine,
    JournalItem,
    Journal,
)


class ClientAdmin(EntityAdmin):
    view_template = "client_view.html"


class ProductAdmin(EntityAdmin):
    pass


class SimpleSalesAdmin(TransactionAdmin):
    pass


erp_admin_site.register(Client, ClientAdmin)
erp_admin_site.register(Product, ProductAdmin)
erp_admin_site.register(SimpleSales, SimpleSalesAdmin)


class InvoiceLineAdmin(TransactionItemAdmin):
    fields = ["product", "quantity", "discount", "value"]
    model = InvoiceLine
    autocomplete_fields = ["product"]


class InvoiceAdmin(TransactionAdmin):
    fields = [("slug", "date"), "client"]
    autocomplete_fields = ["client"]
    inlines = [InvoiceLineAdmin]
    copy_to_formset = ["client"]


erp_admin_site.register(Invoice, InvoiceAdmin)


class JournalItemInline(PrepopulatedInlineMixin, TransactionItemAdmin):
    model = JournalItem
    can_delete = False
    fields = ("client", "value", "data")
    prepopulation_field = "client"
    prepopulation_queryset = Client.objects.order_by("pk")
    computed_fields = {"value": "1 + 1"}
    total_fields = ("value",)

    def get_prepopulation_extra_data(self, request, obj, entity_ids):
        return {pk: {"data": f"row-{pk}"} for pk in entity_ids}


class MovementPrepopulatedAdmin(HeaderLookupAdminMixin, TransactionAdmin):
    fields = ("slug", "date", "data")
    date_hierarchy = None
    inlines = [JournalItemInline]
    header_lookup_fields = ("data",)
    reload_add_on_header_change = True


erp_admin_site.register(Journal, MovementPrepopulatedAdmin)

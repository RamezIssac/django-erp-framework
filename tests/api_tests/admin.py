from erp_framework.admin.admin import EntityAdmin, TransactionAdmin, TransactionItemAdmin
from erp_framework.sites import erp_admin_site

from .models import Customer, Item, Order, OrderLine

calls = []


class CustomerAdmin(EntityAdmin):
    pass


class ItemAdmin(EntityAdmin):
    pass


class OrderLineInline(TransactionItemAdmin):
    model = OrderLine
    fields = ["item", "quantity", "price"]
    extra = 0


class OrderAdmin(TransactionAdmin):
    fields = [("slug", "date"), "customer", "notes"]
    inlines = [OrderLineInline]
    # API twin: the detail payload also exposes the computed value (not on the form)
    api_detail_fields = ["slug", "date", "customer", "notes", "value"]

    def whole_changeform_validation(self, request, form, formsets, change, **kwargs):
        calls.append(("whole_changeform_validation", request.is_api))
        if form.cleaned_data.get("notes") == "reject":
            form.add_error(None, "Rejected by whole_changeform_validation.")
            return False
        return True

    def pre_save(self, form, formsets, change):
        calls.append(("pre_save", change))

    def post_save(self, request, new_object, form, formsets, change):
        calls.append(("post_save", change))
        total = sum(line.value for line in new_object.lines.all())
        if total != new_object.value:
            new_object.value = total
            new_object.save()


erp_admin_site.register(Customer, CustomerAdmin)
erp_admin_site.register(Item, ItemAdmin)
erp_admin_site.register(Order, OrderAdmin)

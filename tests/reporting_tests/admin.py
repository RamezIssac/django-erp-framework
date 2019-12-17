from ra.admin.admin import RaAdmin, ra_admin_site, RaMovementAdmin
from .models import Client, Product, SimpleSales


class ClientAdmin(RaAdmin):
    view_template = 'client_view.html'


class ProductAdmin(RaAdmin):
    pass


class SimpleSalesAdmin(RaMovementAdmin):
    pass


ra_admin_site.register(Client, ClientAdmin)
ra_admin_site.register(Product, ProductAdmin)
ra_admin_site.register(SimpleSales, SimpleSalesAdmin)

from ra.admin.admin import RaAdmin, ra_admin_site
from .models import Client, Product


class ClientAdmin(RaAdmin):
    view_template = 'client_view.html'


class ProductAdmin(RaAdmin):
    pass


ra_admin_site.register(Client, ClientAdmin)
ra_admin_site.register(Product, ProductAdmin)

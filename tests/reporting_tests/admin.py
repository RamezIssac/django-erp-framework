from ra.admin.admin import RaAdmin, ra_admin_site
from .models import Client


class ClientAdmin(RaAdmin):
    view_template = 'client_view.html'


ra_admin_site.register(Client, ClientAdmin)

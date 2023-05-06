from erp_framework.admin.admin import EntityAdmin, erp_admin_site
from .models import Treasury


class TreasuryAdmin(EntityAdmin):
    pass


erp_admin_site.register(Treasury, TreasuryAdmin)

from ra.admin.admin import EntityAdmin, ra_admin_site
from .models import Treasury


class TreasuryAdmin(EntityAdmin):
    pass


ra_admin_site.register(Treasury, TreasuryAdmin)

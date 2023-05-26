from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.models import Group

from .models import UserReportPermission, GroupReportPermission
from erp_framework.sites import erp_admin_site

User = get_user_model()


class ReportingPermissionInline(admin.TabularInline):
    model = UserReportPermission
    extra = 0
    fields = ("report", "view", "print", "export")  # , "deleted")


class ReportGroupPermissionInline(admin.TabularInline):
    model = GroupReportPermission
    extra = 0
    fields = ("report", "view", "print", "export")


class CustomUserAdmin(UserAdmin):
    inlines = [ReportingPermissionInline]


try:
    admin.site.unregister(User, site=erp_admin_site)
except:
    pass

erp_admin_site.register(User, CustomUserAdmin)


class CustomGroup(GroupAdmin):
    inlines = [ReportGroupPermissionInline]


try:
    admin.site.unregister(Group, site=erp_admin_site)
except:
    pass
erp_admin_site.register(Group, CustomGroup)

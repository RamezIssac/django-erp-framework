from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, Permission
from django.utils.translation import gettext_lazy as _

from .models import GroupReportPermission, UserReportPermission
from erp_framework.sites import erp_admin_site

User = get_user_model()


def _allowed_report_choices_for_user(user):
    from erp_framework.base.app_settings import ERP_FRAMEWORK_SITE_NAME
    from erp_framework.reporting.registry import report_registry

    user_codenames = set(
        user.user_permissions.filter(codename__startswith="view_").values_list("codename", flat=True)
    )
    group_codenames = set(
        Permission.objects.filter(
            group__in=user.groups.all(), codename__startswith="view_"
        ).values_list("codename", flat=True)
    )
    allowed = {c[5:] for c in (user_codenames | group_codenames)}
    return [
        (r.get_report_code(), str(r.report_title))
        for r in report_registry.get_all_reports(admin_site=ERP_FRAMEWORK_SITE_NAME)
        if r.base_model and r.base_model._meta.model_name in allowed
    ]


def _allowed_report_choices_for_group(group):
    from erp_framework.base.app_settings import ERP_FRAMEWORK_SITE_NAME
    from erp_framework.reporting.registry import report_registry

    codenames = set(
        group.permissions.filter(codename__startswith="view_").values_list("codename", flat=True)
    )
    allowed = {c[5:] for c in codenames}
    return [
        (r.get_report_code(), str(r.report_title))
        for r in report_registry.get_all_reports(admin_site=ERP_FRAMEWORK_SITE_NAME)
        if r.base_model and r.base_model._meta.model_name in allowed
    ]


def _make_report_form(model_cls, choices):
    class _Form(forms.ModelForm):
        report_code = forms.ChoiceField(
            choices=[("", "---------")] + choices,
            label=_("Report"),
        )

        class Meta:
            model = model_cls
            fields = ("report_code", "view", "print", "export")

    return _Form


class ReportingPermissionInline(admin.TabularInline):
    model = UserReportPermission
    extra = 1

    def get_formset(self, request, obj=None, **kwargs):
        if obj is not None:
            kwargs["form"] = _make_report_form(
                UserReportPermission, _allowed_report_choices_for_user(obj)
            )
        return super().get_formset(request, obj, **kwargs)


class ReportGroupPermissionInline(admin.TabularInline):
    model = GroupReportPermission
    extra = 1

    def get_formset(self, request, obj=None, **kwargs):
        if obj is not None:
            kwargs["form"] = _make_report_form(
                GroupReportPermission, _allowed_report_choices_for_group(obj)
            )
        return super().get_formset(request, obj, **kwargs)


class CustomUserAdmin(UserAdmin):
    inlines = [ReportingPermissionInline]


try:
    admin.site.unregister(User, site=erp_admin_site)
except Exception:
    pass

erp_admin_site.register(User, CustomUserAdmin)


class CustomGroup(GroupAdmin):
    inlines = [ReportGroupPermissionInline]


try:
    admin.site.unregister(Group, site=erp_admin_site)
except Exception:
    pass
erp_admin_site.register(Group, CustomGroup)

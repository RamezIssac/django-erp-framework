from django.apps import AppConfig

from django.utils.translation import gettext_lazy as _


class ERPFrameworkConfig(AppConfig):
    name = "erp_framework"
    verbose_name = _("ERP framework")

    # def ready(self):
    from django.db.models.signals import post_migrate

    #     super(RaConfig, self).ready()
    #     from .utils.permissions import create_report_permissions
    #     from . import checks
    #
    #     post_migrate.connect(
    #         create_report_permissions,
    #         sender=self,
    #         dispatch_uid="erp_framework.utils.permissions.create_reports_permissions",
    #     )

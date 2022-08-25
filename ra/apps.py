from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _


class RaConfig(AppConfig):
    name = 'ra'
    verbose_name = _('Ra Core App')

    def ready(self):
        super(RaConfig, self).ready()
        from .utils.permissions import create_report_permissions
        from . import checks

        post_migrate.connect(
            create_report_permissions, sender=self,
            dispatch_uid="ra.utils.permissions.create_reports_permissions"
        )

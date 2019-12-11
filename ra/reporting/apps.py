from django import apps
from django.db.models.signals import post_migrate


class ReportAppConfig(apps.AppConfig):
    label = 'Ra Reports'
    name = 'ra.reporting'

    def ready(self):
        from ra.utils.permissions import create_report_permissions
        super().ready()
        post_migrate.connect(
            create_report_permissions, sender=self)

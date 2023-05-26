from django import apps
from django.db import ProgrammingError, OperationalError
from django.db.models.signals import post_migrate


def autodiscover():
    import os
    import sys
    import copy
    from django.utils.module_loading import module_has_submodule

    from importlib import import_module
    from django.apps import apps

    mods = [
        (app_config.name, app_config.module) for app_config in apps.get_app_configs()
    ]

    for app, mod in mods:
        # Attempt to import the app's reports module.
        module = "%s.reports" % app
        try:
            import_module(module)
        except ImportError as e:
            if str(e) == f"No module named '{module}'":
                pass
            else:
                raise e


def sync_reports():
    from .models import Reports
    from .registry import report_registry

    reports = report_registry.get_all_reports()

    try:
        reports_in_db = list(Reports.objects.all().values_list("code", flat=True))
    except (ProgrammingError, OperationalError):
        # Before first migrations
        return

    for report_klass in reports:
        code = f"{report_klass.get_base_model_name()}.{report_klass.get_report_slug()}"
        c, created = Reports.objects.update_or_create(
            code=code,
        )
        c.deleted = False
        c.save()
        try:
            reports_in_db.remove(code)
        except ValueError:
            pass

    Reports.objects.filter(code__in=reports_in_db).update(deleted=True)


class ERPFrameworkReportingAppConfig(apps.AppConfig):
    name = "erp_framework.reporting"

    def ready(self):
        super().ready()
        autodiscover()
        sync_reports()

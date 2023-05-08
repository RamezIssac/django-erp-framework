from django import apps
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
        # Attempt to import the app's translation module.
        module = "%s.reports" % app
        # before_import_registry = copy.copy(translator._registry)
        try:
            import_module(module)
        except ImportError:
            pass


class ERPFrameworkReportingAppConfig(apps.AppConfig):
    name = "erp_framework.reporting"

    def ready(self):
        from erp_framework.utils.permissions import create_report_permissions

        super().ready()
        autodiscover()
        # post_migrate.connect(create_report_permissions, sender=self)

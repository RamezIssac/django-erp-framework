from django.apps import apps
from django.core.management import call_command
from django.test import TestCase

ERP_APPS = [config for config in apps.get_app_configs() if config.name.startswith("erp_framework")]


class MigrationsTest(TestCase):
    def test_no_missing_migrations(self):
        call_command("makemigrations", *[config.label for config in ERP_APPS], "--check", "--dry-run")

    def test_apps_with_tables_pin_default_auto_field(self):
        """Migrations then match the project's DEFAULT_AUTO_FIELD, whatever it is."""
        for config in ERP_APPS:
            if any(not model._meta.proxy for model in config.get_models()):
                with self.subTest(config.name):
                    self.assertIn("default_auto_field", type(config).__dict__)

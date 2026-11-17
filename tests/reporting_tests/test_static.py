import tempfile

from django import test
from django.core.management import call_command
from django.forms import Media

from erp_framework.admin.admin import EntityAdmin


class TestAdminMediaStaticFiles(test.SimpleTestCase):
    def test_entity_admin_media_resolves_under_manifest_storage(self):
        with tempfile.TemporaryDirectory() as static_root:
            with test.override_settings(
                STATIC_ROOT=static_root,
                STORAGES={
                    "default": {
                        "BACKEND": "django.core.files.storage.FileSystemStorage"
                    },
                    "staticfiles": {
                        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
                    },
                },
            ):
                call_command(
                    "collectstatic",
                    interactive=False,
                    verbosity=0,
                    ignore_patterns=["vendor"],
                )
                html = str(Media(EntityAdmin.Media))
        self.assertIn("select2_compat", html)

import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from erp_framework.docs import pages as docs_pages

User = get_user_model()

PERM = "docs_tests.view_secretdocument"

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)


def write_page(directory, name, meta=None, body=""):
    """Write a Markdown page with optional YAML front-matter."""
    lines = []
    if meta:
        lines.append("---")
        for key, value in meta.items():
            if isinstance(value, (list, tuple)):
                rendered = "[" + ", ".join(f'"{item}"' for item in value) + "]"
            else:
                rendered = str(value)
            lines.append(f"{key}: {rendered}")
        lines.append("---")
    lines.append(body)
    path = Path(directory) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build_sources(tmp):
    """
    Two sources, in settings order: a module's docs (lowest priority) and a
    client project override (listed last, wins on duplicate slugs).
    """
    module = Path(tmp) / "module_docs"
    client = Path(tmp) / "client_docs"

    write_page(
        module,
        "index.md",
        meta={"title": "Guide home", "order": 1},
        body="# Welcome\n\nWelcome to the user guide.",
    )
    write_page(
        module,
        "inventory.md",
        meta={"title": "Inventory guide", "order": 10},
        body="# Inventory\n\nMODULE VERSION",
    )
    write_page(
        module,
        "secret.md",
        meta={"title": "Secret page", "order": 20, "perms": [PERM]},
        body="# Secret\n\nRestricted content.",
    )
    write_page(
        module,
        "reports/sales.md",
        meta={"title": "Sales report", "order": 30, "perms": [PERM]},
        body="# Sales\n\n![Chart](chart.png)",
    )
    write_page(module, "raw.md", body='# Raw\n\n<script>alert("x")</script>')
    write_page(module, "untitled-page.md", body="Just some text, no heading."),
    write_page(
        module,
        "guide.md",
        meta={"title": "Using the app", "order": 15},
        body=(
            "# Usage\n\n"
            "| Item | Quantity |\n"
            "|---|---|\n"
            "| Flour | 10 |\n\n"
            "![Stock levels](images/stock.png)\n\n"
            "See the [sales report](reports/sales.md).\n\n"
            ":::warning\n"
            "Watch out\n"
            ":::\n"
        ),
    )
    write_page(
        module,
        "ar/guide.md",
        meta={"title": "دليل الاستخدام"},
        body="# الاستخدام",
    )

    images = module / "images"
    images.mkdir(parents=True, exist_ok=True)
    (images / "stock.png").write_bytes(PNG_BYTES)
    (module / "reports").mkdir(exist_ok=True)
    (module / "reports" / "chart.png").write_bytes(PNG_BYTES)

    # The client project shadows the module's inventory page.
    write_page(
        client,
        "inventory.md",
        meta={"title": "Inventory (customized)", "order": 10},
        body="# Inventory\n\nCLIENT OVERRIDE",
    )

    return module, client


@override_settings(ROOT_URLCONF="docs_tests.urls")
class DocsViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="staff", password="x", is_staff=True
        )
        cls.privileged = User.objects.create_user(
            username="privileged", password="x", is_staff=True
        )
        cls.privileged.user_permissions.add(
            Permission.objects.get(
                codename="view_secretdocument", content_type__app_label="docs_tests"
            )
        )
        cls.superuser = User.objects.create_superuser(
            username="boss", email="b@test.com", password="x"
        )
        cls.plain = User.objects.create_user(username="plain", password="x")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.module_dir, self.client_dir = build_sources(tmp.name)
        override = override_settings(
            ERP_DOCS_SOURCE_DIRS=[str(self.module_dir), str(self.client_dir)]
        )
        override.enable()
        self.addCleanup(override.disable)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("erp_docs:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_non_staff_is_redirected(self):
        self.client.force_login(self.plain)
        response = self.client.get(reverse("erp_docs:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_index_renders_index_page(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("erp_docs:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome to the user guide.")

    def test_pages_use_the_standalone_layout(self):
        self.client.force_login(self.staff)
        for url in (
            reverse("erp_docs:index"),
            reverse("erp_docs:page", kwargs={"page_path": "guide"}),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                content = response.content.decode()
                # Standalone docs chrome, not the admin menu/navbar/breadcrumbs.
                self.assertIn('id="erp-docs-sidebar"', content)
                self.assertIn('id="erp-docs-topbar"', content)
                self.assertNotIn('id="jazzy-sidebar"', content)
                self.assertNotIn('id="jazzy-navigation"', content)
                self.assertNotIn("breadcrumb", content)
                # The sidebar holds the docs page list...
                self.assertIn("Inventory (customized)", content)
                # ... and the top bar links back to the application.
                self.assertIn('href="/admin/"', content)
                self.assertIn("Back to the application", content)

    def test_current_page_is_highlighted_in_the_docs_nav(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("erp_docs:page", kwargs={"page_path": "guide"})
        )
        content = response.content.decode()
        self.assertIn('class="nav-link active"', content)
        # exactly one highlighted entry, the current page
        self.assertEqual(content.count('class="nav-link active"'), 1)

    def test_rtl_direction_with_bidi_language(self):
        self.client.force_login(self.staff)
        with translation.override("ar"):
            response = self.client.get(
                reverse("erp_docs:page", kwargs={"page_path": "guide"})
            )
        content = response.content.decode()
        self.assertIn('lang="ar"', content)
        self.assertIn('dir="rtl"', content)
        self.assertIn("tabler.rtl.min.css", content)

    def test_index_lists_only_visible_pages(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("erp_docs:index"))
        content = response.content.decode()
        self.assertIn("Inventory (customized)", content)
        self.assertIn("Guide home", content)
        self.assertNotIn("Secret page", content)
        self.assertNotIn("Sales report", content)

    def test_privileged_user_sees_restricted_pages_in_list(self):
        self.client.force_login(self.privileged)
        response = self.client.get(reverse("erp_docs:index"))
        content = response.content.decode()
        self.assertIn("Secret page", content)
        self.assertIn("Sales report", content)

    def test_page_list_is_ordered_by_front_matter(self):
        self.client.force_login(self.privileged)
        response = self.client.get(reverse("erp_docs:index"))
        content = response.content.decode()
        positions = [
            content.index(title)
            for title in (
                "Guide home",
                "Inventory (customized)",
                "Secret page",
                "Sales report",
                "Untitled Page",
            )
        ]
        self.assertEqual(positions, sorted(positions))

    def test_page_rendering(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("erp_docs:page", kwargs={"page_path": "guide"})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Markdown features
        self.assertIn("<table>", content)
        self.assertIn('class="alert alert-warning"', content)
        # Raw assets and links are rewritten to the gated views
        self.assertIn('src="/docs/assets/images/stock.png"', content)
        self.assertIn('href="/docs/reports/sales/"', content)

    def test_shadowing_last_source_wins(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("erp_docs:page", kwargs={"page_path": "inventory"})
        )
        content = response.content.decode()
        self.assertIn("CLIENT OVERRIDE", content)
        self.assertNotIn("MODULE VERSION", content)
        # ... and the page list shows the shadowing page only once
        self.assertEqual(content.count('href="/docs/inventory/"'), 1)

    def test_default_title_from_slug(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("erp_docs:index"))
        self.assertContains(response, "Untitled Page")

    def test_direct_url_denied_returns_404(self):
        self.client.force_login(self.staff)
        for slug in ("secret", "reports/sales"):
            with self.subTest(slug=slug):
                response = self.client.get(
                    reverse("erp_docs:page", kwargs={"page_path": slug})
                )
                self.assertEqual(response.status_code, 404)

    def test_privileged_user_can_open_restricted_page(self):
        self.client.force_login(self.privileged)
        response = self.client.get(
            reverse("erp_docs:page", kwargs={"page_path": "secret"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Restricted content.")

    def test_superuser_passes_page_perms(self):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("erp_docs:page", kwargs={"page_path": "secret"})
        )
        self.assertEqual(response.status_code, 200)

    def test_unknown_page_is_404(self):
        self.client.force_login(self.staff)
        response = self.client.get("/docs/no-such-page/")
        self.assertEqual(response.status_code, 404)

    def test_raw_html_is_escaped(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("erp_docs:page", kwargs={"page_path": "raw"})
        )
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert")

    def test_image_is_served_with_content_type(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("erp_docs:asset", kwargs={"asset_path": "images/stock.png"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(b"".join(response.streaming_content), PNG_BYTES)

    def test_image_inherits_page_permissions(self):
        for user, expected in ((self.staff, 404), (self.privileged, 200)):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(
                    reverse(
                        "erp_docs:asset", kwargs={"asset_path": "reports/chart.png"}
                    )
                )
                self.assertEqual(response.status_code, expected)

    def test_asset_view_never_serves_markdown_sources(self):
        self.client.force_login(self.superuser)
        for asset_path in ("secret.md", "reports/sales.md"):
            with self.subTest(asset_path=asset_path):
                response = self.client.get(
                    reverse("erp_docs:asset", kwargs={"asset_path": asset_path})
                )
                self.assertEqual(response.status_code, 404)

    def test_missing_asset_is_404(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("erp_docs:asset", kwargs={"asset_path": "images/missing.png"})
        )
        self.assertEqual(response.status_code, 404)

    def test_traversal_is_blocked(self):
        self.client.force_login(self.superuser)
        for path in ("/docs/assets/../../tests/runtests.py", "/docs/assets/../secret.md"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_private_paths_are_not_served(self):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("erp_docs:asset", kwargs={"asset_path": ".git/config"})
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(ERP_DOCS_ACCESS_FUNCTION="docs_tests.helpers.deny_all")
    def test_access_function_locks_the_whole_guide(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("erp_docs:index")).status_code, 404)
        self.assertEqual(
            self.client.get(
                reverse("erp_docs:page", kwargs={"page_path": "inventory"})
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("erp_docs:asset", kwargs={"asset_path": "images/stock.png"})
            ).status_code,
            404,
        )


JAZZY_INTEGRATION_APP = "erp_framework.admin.jazzy_tabler_integration"


def installed_apps_with_jazzy_integration():
    """Test INSTALLED_APPS plus the jazzy_tabler integration app (before the theme)."""
    apps = list(settings.INSTALLED_APPS)
    if JAZZY_INTEGRATION_APP not in apps:
        apps.insert(apps.index("jazzy_tabler"), JAZZY_INTEGRATION_APP)
    return apps


@override_settings(
    ROOT_URLCONF="docs_tests.urls",
    INSTALLED_APPS=installed_apps_with_jazzy_integration(),
)
class AdminGuideLinkTest(TestCase):
    """The built-in "User guide" link in the admin chrome (jazzy_tabler)."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="staff-link", password="x", is_staff=True
        )

    def test_admin_shows_the_guide_link(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Top navbar entry, opening the guide in a new tab...
        self.assertIn('id="erp-docs-admin-link"', content)
        self.assertIn('href="/docs/"', content)
        self.assertIn('target="_blank"', content)
        # ... and a sidebar entry (the only chrome on small screens).
        self.assertIn('id="erp-docs-admin-sidebar-link"', content)

    @override_settings(ERP_DOCS_SHOW_ADMIN_LINK=False)
    def test_admin_link_hidden_when_disabled(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('id="erp-docs-admin-link"', content)
        self.assertNotIn('id="erp-docs-admin-sidebar-link"', content)
        self.assertNotIn('href="/docs/"', content)

    @override_settings(ERP_DOCS_ACCESS_FUNCTION="docs_tests.helpers.deny_all")
    def test_admin_link_hidden_without_guide_access(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('id="erp-docs-admin-link"', content)
        self.assertNotIn('id="erp-docs-admin-sidebar-link"', content)


class LanguageSubdirTest(TestCase):
    """Resolution honors a per-language subdirectory of a source."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.module_dir, self.client_dir = build_sources(tmp.name)
        override = override_settings(
            ERP_DOCS_SOURCE_DIRS=[str(self.module_dir), str(self.client_dir)]
        )
        override.enable()
        self.addCleanup(override.disable)

    def test_language_subdir_shadows_source_root(self):
        with translation.override("ar"):
            page = docs_pages.get_page("guide")
            self.assertEqual(page.title, "دليل الاستخدام")

    def test_language_subdir_falls_back_to_source_root(self):
        with translation.override("en"):
            page = docs_pages.get_page("guide")
            self.assertEqual(page.title, "Using the app")

    def test_shadowing_spans_languages(self):
        # The client project's page shadows the module page in every
        # language; the client project provides its own translations.
        with translation.override("ar"):
            page = docs_pages.get_page("inventory")
            self.assertEqual(page.title, "Inventory (customized)")

    def test_language_dirs_are_not_pages(self):
        slugs = docs_pages.get_pages()
        self.assertNotIn("ar/guide", slugs)

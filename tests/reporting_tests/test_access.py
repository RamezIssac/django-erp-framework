from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from erp_framework.base.helpers import admin_site_access_permission
from erp_framework.reporting.models import UserReportPermission
from erp_framework.sites import erp_admin_site

from .models import Client
from .reports import ClientTotalBalance
from .tests import BaseTestData

User = get_user_model()
REPORT_URL_ARGS = ("client", "balances")


def grant_view_client(user):
    user.user_permissions.add(Permission.objects.get(codename="view_client"))


@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class ReportExportPermissionTest(BaseTestData, TestCase):
    """Report `_export` requests are gated by the `export` / `print` report permissions."""

    def get_report(self, **params):
        self.client.login(username="limited", password="password")
        return self.client.get(reverse("erp_framework:report", args=REPORT_URL_ARGS), data=params)

    def grant(self, **flags):
        UserReportPermission.objects.create(
            user=self.limited_user, report_code=ClientTotalBalance.get_report_code(), **flags
        )

    def test_view_without_export_is_denied_csv(self):
        self.grant(view=True, export=False, print=True)
        self.assertEqual(self.get_report(_export="csv").status_code, 403)
        self.assertEqual(self.get_report(_export="print").status_code, 200)
        self.assertEqual(self.get_report().status_code, 200)

    def test_view_without_print_is_denied_print(self):
        self.grant(view=True, export=True, print=False)
        self.assertEqual(self.get_report(_export="print").status_code, 403)
        response = self.get_report(_export="csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])


@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class ReportStaffRequiredTest(BaseTestData, TestCase):
    """Report URLs go through `admin_view`: non-staff users are sent to the admin login."""

    def test_non_staff_with_view_permission_is_redirected(self):
        user = User.objects.create_user(username="portal", password="password")
        grant_view_client(user)
        self.client.login(username="portal", password="password")
        response = self.client.get(reverse("erp_framework:report", args=REPORT_URL_ARGS))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("erp_framework:login"), response["Location"])


@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class GetBySlugPermissionTest(BaseTestData, TestCase):
    """`get_by_slug` needs view or change permission and only finds rows in `get_queryset`."""

    def get_by_slug(self):
        self.client.login(username="limited", password="password")
        url = reverse("erp_framework:reporting_tests_client_get-by-slug", args=(self.client1.slug,))
        return self.client.get(url)

    def test_denied_without_permission(self):
        self.assertEqual(self.get_by_slug().status_code, 403)

    def test_redirects_with_view_permission(self):
        grant_view_client(self.limited_user)
        self.assertEqual(self.get_by_slug().status_code, 302)

    def test_respects_get_queryset(self):
        grant_view_client(self.limited_user)
        client_admin = erp_admin_site._registry[Client]
        with mock.patch.object(client_admin, "get_queryset", return_value=Client.objects.none()):
            self.assertEqual(self.get_by_slug().status_code, 404)


@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class EntityChangelistMarkupTest(BaseTestData, TestCase):
    """Entity names in the changelist title and stats columns are HTML-escaped."""

    def test_entity_name_is_escaped(self):
        Client.objects.create(name="A & B <C>", lastmod_user=self.user)
        self.client.login(username="super", password="secret")
        response = self.client.get(reverse("erp_framework:reporting_tests_client_changelist"))
        content = response.content.decode()
        self.assertIn(">A &amp; B &lt;C&gt;</a>", content)
        self.assertIn('name="Statistics for A &amp; B &lt;C&gt;"', content)
        self.assertNotIn("<C>", content)


class AdminSiteAccessPermissionTest(TestCase):
    """DEBUG does not widen admin site access: active staff only."""

    @override_settings(DEBUG=True)
    def test_debug_does_not_admit_non_staff(self):
        request = RequestFactory().get("/")
        request.user = User.objects.create_user(username="portal", password="password")
        self.assertFalse(admin_site_access_permission(request))
        request.user.is_staff = True
        self.assertTrue(admin_site_access_permission(request))

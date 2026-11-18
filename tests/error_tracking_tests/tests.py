from unittest import mock

from django.apps import apps
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from erp_framework.base.error_tracking import start_error_tracking
from erp_framework.sites import erp_admin_site

ERROR_TRACKING = {
    "dsn": "https://public@glitchtip.example.com/2",
    "environment": "staging",
    "release": "my-app@abc123",
}
WITH_DSN = override_settings(ERP_FRAMEWORK_SETTINGS={"error_tracking": ERROR_TRACKING})
BROWSER_BUNDLE = "https://browser.sentry-cdn.com/11.14.0/bundle.min.js"


@mock.patch("erp_framework.base.error_tracking.ignore_logger")
@mock.patch("erp_framework.base.error_tracking.sentry_sdk.init")
class StartErrorTrackingTest(SimpleTestCase):
    @override_settings(ERP_FRAMEWORK_SETTINGS={})
    def test_no_op_without_dsn(self, sdk_init, ignore_logger):
        self.assertFalse(start_error_tracking())
        sdk_init.assert_not_called()
        ignore_logger.assert_not_called()

    @WITH_DSN
    def test_starts_sdk_with_privacy_defaults(self, sdk_init, ignore_logger):
        self.assertTrue(start_error_tracking())
        sdk_init.assert_called_once_with(
            dsn=ERROR_TRACKING["dsn"],
            environment="staging",
            release="my-app@abc123",
            send_default_pii=False,
            max_request_body_size="never",
            include_local_variables=False,
            traces_sample_rate=0.0,
        )
        ignore_logger.assert_called_once_with("django.channels.server")

    @override_settings(
        ERP_FRAMEWORK_SETTINGS={
            "error_tracking": {**ERROR_TRACKING, "include_local_variables": True}
        }
    )
    def test_local_variables_opt_in(self, sdk_init, ignore_logger):
        start_error_tracking()
        self.assertIs(sdk_init.call_args.kwargs["include_local_variables"], True)

    @WITH_DSN
    def test_app_ready_starts_error_tracking(self, sdk_init, ignore_logger):
        apps.get_app_config("erp_framework").ready()
        self.assertEqual(sdk_init.call_args.kwargs["dsn"], ERROR_TRACKING["dsn"])


@override_settings(ROOT_URLCONF="error_tracking_tests.urls")
class SentryBrowserSnippetTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="admin", password="admin", email=""
        )

    def admin_request(self):
        request = RequestFactory().get("/")
        request.user = self.admin
        return request

    def render_erp_base_site(self):
        request = self.admin_request()
        return render_to_string(
            "erp_framework/base_site.html",
            erp_admin_site.each_context(request),
            request=request,
        )

    @WITH_DSN
    def test_each_context_exposes_browser_values_only(self):
        context = erp_admin_site.each_context(self.admin_request())
        self.assertEqual(context["error_tracking"], ERROR_TRACKING)

    @WITH_DSN
    def test_login_page_loads_browser_sdk_with_dsn(self):
        response = self.client.get(reverse("erp_framework:login"))
        self.assertContains(response, BROWSER_BUNDLE)
        self.assertContains(response, 'dsn: "https://public@glitchtip.example.com/2"')
        self.assertContains(response, 'environment: "staging"')

    @WITH_DSN
    def test_erp_base_site_loads_browser_sdk_with_dsn(self):
        self.assertEqual(self.render_erp_base_site().count(BROWSER_BUNDLE), 1)

    @override_settings(ERP_FRAMEWORK_SETTINGS={})
    def test_no_browser_sdk_without_dsn(self):
        login = self.client.get(reverse("erp_framework:login"))
        self.assertNotContains(login, BROWSER_BUNDLE)
        self.assertNotIn(BROWSER_BUNDLE, self.render_erp_base_site())

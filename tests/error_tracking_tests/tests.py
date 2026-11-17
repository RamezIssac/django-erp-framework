import copy
import os
import sys
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from erp_framework.base.error_tracking import init_sentry
from erp_framework.context_processors import sentry

SENTRY_ENV = {
    "SENTRY_DSN": "https://public@glitchtip.example.com/2",
    "SENTRY_ENVIRONMENT": "staging",
    "SENTRY_RELEASE": "my-app@abc123",
}
NO_SENTRY_ENV = {"SENTRY_DSN": "", "SENTRY_ENVIRONMENT": "", "SENTRY_RELEASE": ""}
BROWSER_BUNDLE = "https://browser.sentry-cdn.com/11.14.0/bundle.min.js"


def templates_with_sentry_processor():
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]["OPTIONS"]["context_processors"].append(
        "erp_framework.context_processors.sentry"
    )
    return templates


class InitSentryTest(SimpleTestCase):
    def test_no_op_without_dsn(self):
        with mock.patch.dict(os.environ, NO_SENTRY_ENV), mock.patch(
            "sentry_sdk.init"
        ) as sdk_init:
            self.assertFalse(init_sentry())
        sdk_init.assert_not_called()

    def test_no_op_without_sentry_sdk(self):
        with mock.patch.dict(os.environ, SENTRY_ENV), mock.patch.dict(
            sys.modules, {"sentry_sdk": None}
        ):
            self.assertFalse(init_sentry())

    def test_starts_sdk_with_privacy_defaults(self):
        with mock.patch.dict(os.environ, SENTRY_ENV), mock.patch(
            "sentry_sdk.init"
        ) as sdk_init, mock.patch(
            "sentry_sdk.integrations.logging.ignore_logger"
        ) as ignore_logger:
            self.assertTrue(init_sentry())
        sdk_init.assert_called_once_with(
            dsn=SENTRY_ENV["SENTRY_DSN"],
            environment="staging",
            release="my-app@abc123",
            send_default_pii=False,
            max_request_body_size="never",
            include_local_variables=False,
            traces_sample_rate=0.0,
        )
        ignore_logger.assert_called_once_with("django.channels.server")

    def test_local_variables_opt_in(self):
        with mock.patch.dict(os.environ, SENTRY_ENV), mock.patch(
            "sentry_sdk.init"
        ) as sdk_init, mock.patch("sentry_sdk.integrations.logging.ignore_logger"):
            init_sentry(include_local_variables=True)
        self.assertIs(sdk_init.call_args.kwargs["include_local_variables"], True)


class SentryContextProcessorTest(SimpleTestCase):
    def test_exposes_env_values(self):
        with mock.patch.dict(os.environ, SENTRY_ENV):
            self.assertEqual(sentry(RequestFactory().get("/")), SENTRY_ENV)

    def test_empty_values_without_env(self):
        with mock.patch.dict(os.environ, NO_SENTRY_ENV):
            self.assertEqual(sentry(RequestFactory().get("/")), NO_SENTRY_ENV)


@override_settings(
    ROOT_URLCONF="error_tracking_tests.urls",
    TEMPLATES=templates_with_sentry_processor(),
)
class SentryBrowserSnippetTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="admin", password="admin", email=""
        )

    def test_login_page_loads_browser_sdk_with_dsn(self):
        with mock.patch.dict(os.environ, SENTRY_ENV):
            response = self.client.get(reverse("erp_framework:login"))
        self.assertContains(response, BROWSER_BUNDLE)
        self.assertContains(response, 'dsn: "https://public@glitchtip.example.com/2"')
        self.assertContains(response, 'environment: "staging"')

    def render_erp_base_site(self):
        request = RequestFactory().get("/")
        request.user = self.admin
        return render_to_string("erp_framework/base_site.html", request=request)

    def test_erp_base_site_loads_browser_sdk_with_dsn(self):
        with mock.patch.dict(os.environ, SENTRY_ENV):
            html = self.render_erp_base_site()
        self.assertEqual(html.count(BROWSER_BUNDLE), 1)

    def test_no_browser_sdk_without_dsn(self):
        with mock.patch.dict(os.environ, NO_SENTRY_ENV):
            login = self.client.get(reverse("erp_framework:login"))
            html = self.render_erp_base_site()
        self.assertNotContains(login, BROWSER_BUNDLE)
        self.assertNotIn(BROWSER_BUNDLE, html)

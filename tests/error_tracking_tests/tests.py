import importlib.machinery
import sys
import types
from unittest import mock

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.signals import got_request_exception
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from erp_framework.checks import check_error_tracking
from erp_framework.error_tracking import get_backend
from erp_framework.sites import erp_admin_site

from .backends import RecordingBackend


def fake_modules(spec):
    """sys.modules entries for fake SDK packages: {"pkg.sub": {"attr": value}}."""
    modules = {}
    for dotted, attrs in spec.items():
        parts = dotted.split(".")
        for depth in range(1, len(parts) + 1):
            name = ".".join(parts[:depth])
            if name not in modules:
                module = types.ModuleType(name)
                module.__spec__ = importlib.machinery.ModuleSpec(name, None)
                modules[name] = module
                if depth > 1:
                    setattr(modules[".".join(parts[: depth - 1])], parts[depth - 1], module)
        for attr, value in attrs.items():
            setattr(modules[dotted], attr, value)
    return modules


def error_tracking(backend, options):
    return override_settings(
        ERP_FRAMEWORK_SETTINGS={"error_tracking": {"backend": backend, "options": options}}
    )


def start_server():
    apps.get_app_config("erp_framework").ready()


BACKENDS = {
    "sentry": {
        "sdk": "sentry_sdk",
        "modules": lambda: {
            "sentry_sdk": {"init": mock.Mock()},
            "sentry_sdk.integrations.logging": {"ignore_logger": mock.Mock()},
        },
        "options": {"dsn": "https://public@glitchtip.example.com/2", "environment": "staging"},
        "server_init": "sentry_sdk",
        "snippet": "https://browser.sentry-cdn.com/11.14.0/bundle.min.js",
    },
    "rollbar": {
        "sdk": "rollbar",
        "modules": lambda: {"rollbar": {"init": mock.Mock(), "report_exc_info": mock.Mock()}},
        "options": {"access_token": "server-token", "client_token": "client-token"},
        "server_init": "rollbar",
        "snippet": "https://cdn.jsdelivr.net/npm/rollbar@4.2.1/dist/rollbar.min.js",
    },
    "newrelic": {
        "sdk": "newrelic",
        "modules": lambda: {
            "newrelic.agent": {
                "get_browser_timing_header": mock.Mock(return_value="<script>NREUM-test</script>")
            },
            "newrelic.config": {"_configuration_done": True},
        },
        "options": {"browser_timing_header": True},
        "server_init": None,
        "snippet": "<script>NREUM-test</script>",
    },
    "datadog": {
        "sdk": "ddtrace",
        "modules": lambda: {"ddtrace.bootstrap.sitecustomize": {}},
        "options": {"application_id": "app-id", "client_token": "rum-token"},
        "server_init": None,
        "snippet": "https://cdn.jsdelivr.net/npm/@datadog/browser-rum@7.18.0/bundle/datadog-rum.js",
    },
}


@override_settings(ROOT_URLCONF="error_tracking_tests.urls")
class BuiltinBackendsTest(TestCase):
    """The same contract for every built-in backend, run once per backend."""

    def tearDown(self):
        got_request_exception.disconnect(dispatch_uid="erp_framework.error_tracking.rollbar")

    def for_each_backend(self):
        for name, backend in BACKENDS.items():
            modules = fake_modules(backend["modules"]())
            with self.subTest(backend=name), mock.patch.dict(sys.modules, modules):
                yield name, backend, modules

    def test_configured_backend_starts_server_sdk(self):
        for name, backend, modules in self.for_each_backend():
            with error_tracking(name, backend["options"]):
                start_server()
            if backend["server_init"]:
                modules[backend["server_init"]].init.assert_called_once()

    def test_configured_backend_renders_browser_snippet_on_login_page(self):
        for name, backend, modules in self.for_each_backend():
            with error_tracking(name, backend["options"]):
                response = self.client.get(reverse("erp_framework:login"))
            self.assertContains(response, backend["snippet"], count=1)

    def test_backend_without_credentials_starts_and_renders_nothing(self):
        for name, backend, modules in self.for_each_backend():
            with error_tracking(name, {}):
                start_server()
                response = self.client.get(reverse("erp_framework:login"))
            self.assertNotContains(response, backend["snippet"])
            if backend["server_init"]:
                modules[backend["server_init"]].init.assert_not_called()

    def test_check_reports_missing_sdk(self):
        for name, backend, modules in self.for_each_backend():
            with error_tracking(name, backend["options"]), mock.patch.dict(
                sys.modules, {backend["sdk"]: None}
            ):
                ids = [message.id for message in check_error_tracking()]
                start_server()
            self.assertEqual(ids, ["erp_framework.E010"])

    def test_check_passes_with_sdk_installed(self):
        for name, backend, modules in self.for_each_backend():
            with error_tracking(name, backend["options"]):
                self.assertEqual(check_error_tracking(), [])


@override_settings(ROOT_URLCONF="error_tracking_tests.urls")
class ErrorTrackingOffTest(TestCase):
    @override_settings(ERP_FRAMEWORK_SETTINGS={})
    def test_no_backend_means_nothing_rendered_or_checked(self):
        self.assertIsNone(get_backend())
        self.assertEqual(check_error_tracking(), [])
        response = self.client.get(reverse("erp_framework:login"))
        self.assertNotContains(response, "<script src=\"https://")


class SentryBackendTest(TestCase):
    def test_server_sdk_uses_privacy_defaults(self):
        modules = fake_modules(BACKENDS["sentry"]["modules"]())
        with mock.patch.dict(sys.modules, modules), error_tracking(
            "sentry", {"dsn": "https://k@h/1", "environment": "staging", "release": "app@1"}
        ):
            start_server()
        modules["sentry_sdk"].init.assert_called_once_with(
            dsn="https://k@h/1",
            environment="staging",
            release="app@1",
            send_default_pii=False,
            max_request_body_size="never",
            include_local_variables=False,
            traces_sample_rate=0.0,
        )
        modules["sentry_sdk.integrations.logging"].ignore_logger.assert_called_once_with(
            "django.channels.server"
        )

    @override_settings(ROOT_URLCONF="error_tracking_tests.urls")
    def test_erp_base_site_renders_snippet_once(self):
        admin = get_user_model().objects.create_superuser("admin", "", "admin")
        request = RequestFactory().get("/")
        request.user = admin
        with error_tracking("sentry", BACKENDS["sentry"]["options"]):
            html = render_to_string(
                "erp_framework/base_site.html", erp_admin_site.each_context(request), request=request
            )
        self.assertEqual(html.count(BACKENDS["sentry"]["snippet"]), 1)


class RollbarBackendTest(TestCase):
    def tearDown(self):
        got_request_exception.disconnect(dispatch_uid="erp_framework.error_tracking.rollbar")

    def test_server_sdk_uses_privacy_defaults_and_reports_request_exceptions(self):
        modules = fake_modules(BACKENDS["rollbar"]["modules"]())
        with mock.patch.dict(sys.modules, modules), error_tracking(
            "rollbar", {"access_token": "server-token", "environment": "staging"}
        ):
            start_server()
            request = RequestFactory().get("/")
            try:
                raise ValueError("boom")
            except ValueError:
                got_request_exception.send(sender=None, request=request)
        modules["rollbar"].init.assert_called_once_with(
            "server-token",
            environment="staging",
            code_version=None,
            capture_ip=False,
            include_request_body=False,
            locals={"enabled": False},
        )
        exc_info, reported_request = modules["rollbar"].report_exc_info.call_args.args
        self.assertIs(exc_info[0], ValueError)
        self.assertIs(reported_request, request)

    @override_settings(ROOT_URLCONF="error_tracking_tests.urls")
    def test_browser_gets_the_client_token_only(self):
        with error_tracking("rollbar", BACKENDS["rollbar"]["options"]):
            response = self.client.get(reverse("erp_framework:login"))
        self.assertContains(response, 'accessToken: "client\\u002Dtoken"')
        self.assertNotContains(response, "server-token")


class AgentBackendsTest(TestCase):
    def test_no_warning_when_agent_is_running(self):
        cases = {
            "newrelic": {"newrelic.config": {"_configuration_done": True}},
            "datadog": {"ddtrace.bootstrap.sitecustomize": {}},
        }
        for name, spec in cases.items():
            with self.subTest(backend=name), mock.patch.dict(
                sys.modules, fake_modules(spec)
            ), error_tracking(name, {}):
                self.assertEqual(check_error_tracking(), [])

    def test_check_warns_when_agent_is_not_running(self):
        cases = {
            "newrelic": {"newrelic.agent": {}, "newrelic.config": {"_configuration_done": False}},
            "datadog": {"ddtrace": {}},
        }
        for name, spec in cases.items():
            with self.subTest(backend=name), mock.patch.dict(
                sys.modules, fake_modules(spec)
            ), error_tracking(name, {}):
                self.assertEqual(
                    [message.id for message in check_error_tracking()], ["erp_framework.W010"]
                )


@override_settings(ROOT_URLCONF="error_tracking_tests.urls")
class CustomBackendsTest(TestCase):
    def test_dotted_path_backend_starts_and_renders(self):
        with error_tracking("error_tracking_tests.backends.RecordingBackend", {"api_key": "k1"}):
            start_server()
            response = self.client.get(reverse("erp_framework:login"))
        self.assertEqual(RecordingBackend.started_with, {"api_key": "k1"})
        self.assertContains(response, "https://tracker.example.com/k1.js")

    def test_external_mode_renders_project_template_only(self):
        options = {"template": "error_tracking_tests/external.html", "config": {"api_key": "k2"}}
        with error_tracking("external", options):
            self.assertEqual(check_error_tracking(), [])
            response = self.client.get(reverse("erp_framework:login"))
        self.assertContains(response, "https://tracker.example.com/k2.js")

    def test_external_mode_without_template_fails_check(self):
        with error_tracking("external", {}):
            self.assertEqual(
                [message.id for message in check_error_tracking()], ["erp_framework.E012"]
            )

    def test_unknown_backend_fails_check_and_does_not_break_pages(self):
        with error_tracking("no.such.Backend", {}):
            start_server()
            ids = [message.id for message in check_error_tracking()]
            response = self.client.get(reverse("erp_framework:login"))
        self.assertEqual(ids, ["erp_framework.E011"])
        self.assertEqual(response.status_code, 200)

import importlib.machinery
import sys
import types
from unittest import mock

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import checks
from django.core.signals import got_request_exception
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from erp_framework.checks import check_error_tracking
from erp_framework.error_tracking import get_backend
from erp_framework.error_tracking.backends.base import ErrorTrackingBackend
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
        "class": "SentryBackend",
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
        "class": "RollbarBackend",
        "sdk": "rollbar",
        "modules": lambda: {"rollbar": {"init": mock.Mock(), "report_exc_info": mock.Mock()}},
        "options": {"access_token": "server-token", "client_token": "client-token"},
        "server_init": "rollbar",
        "snippet": "https://cdn.jsdelivr.net/npm/rollbar@4.2.1/dist/rollbar.min.js",
    },
    "newrelic": {
        "class": "NewRelicBackend",
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
        "class": "DatadogBackend",
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

    def test_missing_sdk_message_names_the_extra_to_install(self):
        for name, backend, modules in self.for_each_backend():
            with error_tracking(name, backend["options"]), mock.patch.dict(
                sys.modules, {backend["sdk"]: None}
            ):
                (message,) = check_error_tracking()
            self.assertEqual(
                message.msg,
                f"Error tracking backend {backend['class']} needs {backend['sdk']}, which is not installed.",
            )
            self.assertEqual(message.hint, f"pip install django-erp-framework[{name}]")
            self.assertEqual(message.obj, "ERP_FRAMEWORK_SETTINGS['error_tracking']")

    def test_check_passes_with_sdk_installed(self):
        for name, backend, modules in self.for_each_backend():
            with error_tracking(name, backend["options"]):
                self.assertEqual(check_error_tracking(), [])


@override_settings(ROOT_URLCONF="error_tracking_tests.urls")
class ErrorTrackingOffTest(TestCase):
    def test_check_is_registered_with_django(self):
        self.assertIn(check_error_tracking, checks.registry.registry.get_checks())

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

    def test_local_variables_are_opt_in(self):
        modules = fake_modules(BACKENDS["sentry"]["modules"]())
        with mock.patch.dict(sys.modules, modules), error_tracking(
            "sentry", {"dsn": "https://k@h/1", "include_local_variables": True}
        ):
            start_server()
        self.assertIs(modules["sentry_sdk"].init.call_args.kwargs["include_local_variables"], True)

    def test_browser_config_passes_dsn_environment_and_release(self):
        options = {"dsn": "https://k@h/1", "environment": "staging", "release": "app@1", "secret": "s"}
        with error_tracking("sentry", options):
            self.assertEqual(get_backend().browser_config(None), {k: options[k] for k in ("dsn", "environment", "release")})
        with error_tracking("sentry", {"dsn": "https://k@h/1"}):
            self.assertEqual(
                get_backend().browser_config(None), {"dsn": "https://k@h/1", "environment": "", "release": ""}
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

    def test_server_sdk_options_and_defaults(self):
        modules = fake_modules(BACKENDS["rollbar"]["modules"]())
        options = {"access_token": "t", "code_version": "abc123", "include_local_variables": True}
        with mock.patch.dict(sys.modules, modules), error_tracking("rollbar", options):
            start_server()
        kwargs = modules["rollbar"].init.call_args.kwargs
        self.assertEqual(kwargs["environment"], "production")
        self.assertEqual(kwargs["code_version"], "abc123")
        self.assertEqual(kwargs["locals"], {"enabled": True})
        self.assertTrue(got_request_exception.disconnect(dispatch_uid="erp_framework.error_tracking.rollbar"))

    def test_browser_config_passes_client_token_environment_and_code_version(self):
        options = {"access_token": "server", "client_token": "c", "environment": "e", "code_version": "v"}
        with error_tracking("rollbar", options):
            self.assertEqual(
                get_backend().browser_config(None), {"client_token": "c", "environment": "e", "code_version": "v"}
            )

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

    def test_warning_names_how_to_start_the_agent(self):
        hints = {
            "newrelic": "Start the process with `newrelic-admin run-program`, or call "
            "newrelic.agent.initialize() at the top of wsgi.py / asgi.py.",
            "datadog": "Start the process with `ddtrace-run`, or `import ddtrace.auto` at the top of wsgi.py / asgi.py.",
        }
        cases = {"newrelic": {"newrelic.config": {}}, "datadog": {"ddtrace": {}}}
        for name, spec in cases.items():
            with self.subTest(backend=name), mock.patch.dict(
                sys.modules, fake_modules(spec)
            ), error_tracking(name, {}):
                (message,) = check_error_tracking()
            self.assertEqual(
                message.msg,
                f"Error tracking backend {BACKENDS[name]['class']}: the agent is not running in this process.",
            )
            self.assertEqual(message.hint, hints[name])
            self.assertEqual(message.obj, "ERP_FRAMEWORK_SETTINGS['error_tracking']")

    def test_newrelic_without_its_config_module_is_not_running(self):
        modules = fake_modules({"newrelic": {}})
        modules["newrelic.config"] = None
        with mock.patch.dict(sys.modules, modules), error_tracking("newrelic", {}):
            self.assertEqual([message.id for message in check_error_tracking()], ["erp_framework.W010"])

    def test_datadog_browser_config_passes_rum_keys(self):
        keys = ("application_id", "client_token", "site", "service", "env", "version")
        options = {key: f"{key}-value" for key in keys} | {"api_key": "server-only"}
        with error_tracking("datadog", options):
            self.assertEqual(get_backend().browser_config(None), {key: f"{key}-value" for key in keys})

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

    def test_missing_sdk_hint_without_an_extra_names_the_package(self):
        backend = type("NoExtraBackend", (ErrorTrackingBackend,), {"sdk_module": "no_such_sdk_pkg"})({})
        (message,) = backend.check()
        self.assertEqual((message.id, message.hint), ("erp_framework.E010", "pip install no_such_sdk_pkg"))
        backend.extra = "tracker"
        self.assertEqual(backend.check()[0].hint, "pip install django-erp-framework[tracker]")

    def test_external_mode_renders_project_template_only(self):
        options = {"template": "error_tracking_tests/external.html", "config": {"api_key": "k2"}}
        with error_tracking("external", options):
            self.assertEqual(check_error_tracking(), [])
            response = self.client.get(reverse("erp_framework:login"))
        self.assertContains(response, "https://tracker.example.com/k2.js")

    def test_external_mode_without_template_fails_check(self):
        with error_tracking("external", {}):
            (message,) = check_error_tracking()
        self.assertEqual(message.id, "erp_framework.E012")
        self.assertEqual(message.msg, "The external error tracking backend needs a `template` option.")
        self.assertEqual(message.obj, "ERP_FRAMEWORK_SETTINGS['error_tracking']")

    def test_unknown_backend_check_names_the_builtin_backends(self):
        with error_tracking("no.such.Backend", {}):
            (message,) = check_error_tracking()
        self.assertEqual(message.msg, "Error tracking backend cannot be loaded: No module named 'no'")
        self.assertEqual(
            message.hint, "Use sentry, rollbar, newrelic, datadog, external or a dotted path to a backend class."
        )
        self.assertEqual(message.obj, "ERP_FRAMEWORK_SETTINGS['error_tracking']")

    def test_unknown_backend_fails_check_and_does_not_break_pages(self):
        with error_tracking("no.such.Backend", {}):
            start_server()
            ids = [message.id for message in check_error_tracking()]
            response = self.client.get(reverse("erp_framework:login"))
        self.assertEqual(ids, ["erp_framework.E011"])
        self.assertEqual(response.status_code, 200)


class BaseBackendDefaultsTest(TestCase):
    """A subclass that overrides nothing needs no SDK, starts no agent and renders nothing."""

    def test_bare_subclass_passes_checks_and_renders_nothing(self):
        backend = type("Bare", (ErrorTrackingBackend,), {})({"key": "v"})
        self.assertEqual(backend.check(), [])
        self.assertIsNone(backend.browser_context(None))

    def test_start_hint_alone_does_not_warn(self):
        backend = type("Hinted", (ErrorTrackingBackend,), {"start_hint": "run it"})({})
        self.assertEqual(backend.check(), [])

    def test_stopped_agent_without_start_hint_does_not_warn(self):
        backend = type("Stopped", (ErrorTrackingBackend,), {"agent_started": lambda self: False})({})
        self.assertEqual(backend.check(), [])

    def test_browser_keys_without_requires_or_template(self):
        attrs = {"browser_keys": ("key",)}
        self.assertEqual(type("Keys", (ErrorTrackingBackend,), attrs)({"key": "v"}).browser_config(None), {"key": "v"})
        self.assertIsNone(type("Keys", (ErrorTrackingBackend,), attrs)({"key": "v"}).browser_context(None))

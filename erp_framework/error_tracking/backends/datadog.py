import sys

from .base import ErrorTrackingBackend


class DatadogBackend(ErrorTrackingBackend):
    """Datadog. Server errors come from ddtrace started before Django, browser errors from RUM."""

    sdk_module = "ddtrace"
    extra = "datadog"
    browser_template = "erp_framework/error_tracking/datadog.html"
    browser_keys = ("application_id", "client_token", "site", "service", "env", "version")
    browser_requires = ("application_id", "client_token")
    start_hint = "Start the process with `ddtrace-run`, or `import ddtrace.auto` at the top of wsgi.py / asgi.py."

    def agent_started(self):
        # Loaded by both ddtrace-run and `import ddtrace.auto`.
        return "ddtrace.bootstrap.sitecustomize" in sys.modules

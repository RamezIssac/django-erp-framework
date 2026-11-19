import sys

from .agent import AgentBackend


class DatadogBackend(AgentBackend):
    """Datadog. Server errors come from ddtrace started before Django. Browser options
    (RUM): application_id, client_token, site, service, env, version."""

    sdk_module = "ddtrace"
    extra = "datadog"
    browser_template = "erp_framework/error_tracking/datadog.html"
    start_hint = "Start the process with `ddtrace-run`, or `import ddtrace.auto` at the top of wsgi.py / asgi.py."

    def agent_started(self):
        # Loaded by both ddtrace-run and `import ddtrace.auto`.
        return "ddtrace.bootstrap.sitecustomize" in sys.modules

    def browser_config(self, request):
        if not (self.options.get("application_id") and self.options.get("client_token")):
            return None
        return {
            "application_id": self.options["application_id"],
            "client_token": self.options["client_token"],
            "site": self.options.get("site") or "datadoghq.com",
            "service": self.options.get("service", ""),
            "env": self.options.get("env", ""),
            "version": self.options.get("version", ""),
        }

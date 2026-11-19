import sys

from django.core.signals import got_request_exception

from .base import ErrorTrackingBackend


def report_request_exception(sender, request=None, **kwargs):
    import rollbar

    rollbar.report_exc_info(sys.exc_info(), request)


class RollbarBackend(ErrorTrackingBackend):
    """Rollbar. Options: access_token (server), client_token (browser), environment,
    code_version, include_local_variables."""

    sdk_module = "rollbar"
    extra = "rollbar"
    browser_template = "erp_framework/error_tracking/rollbar.html"

    def init_server(self):
        if not self.options.get("access_token"):
            return
        try:
            import rollbar
        except ImportError:
            return
        rollbar.init(
            self.options["access_token"],
            environment=self.options.get("environment") or "production",
            code_version=self.options.get("code_version") or None,
            capture_ip=False,
            include_request_body=False,
            locals={"enabled": self.options.get("include_local_variables", False)},
        )
        got_request_exception.connect(
            report_request_exception, dispatch_uid="erp_framework.error_tracking.rollbar"
        )

    def browser_config(self, request):
        if not self.options.get("client_token"):
            return None
        return {
            key: self.options.get(key, "")
            for key in ("client_token", "environment", "code_version")
        }

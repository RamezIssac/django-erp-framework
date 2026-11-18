from .base import ErrorTrackingBackend


class SentryBackend(ErrorTrackingBackend):
    """Sentry or GlitchTip. Options: dsn, environment, release, include_local_variables."""

    sdk_module = "sentry_sdk"
    extra = "sentry"
    browser_template = "erp_framework/error_tracking/sentry.html"

    def init_server(self):
        if not self.options.get("dsn"):
            return
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import ignore_logger
        except ImportError:
            return
        sentry_sdk.init(
            dsn=self.options["dsn"],
            environment=self.options.get("environment") or None,
            release=self.options.get("release") or None,
            send_default_pii=False,
            max_request_body_size="never",
            include_local_variables=self.options.get("include_local_variables", False),
            traces_sample_rate=0.0,
        )
        # The dev server's access log repeats every 500 as a second issue.
        ignore_logger("django.channels.server")

    def browser_config(self, request):
        if not self.options.get("dsn"):
            return None
        return {key: self.options.get(key, "") for key in ("dsn", "environment", "release")}

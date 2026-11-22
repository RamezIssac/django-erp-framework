from .base import ErrorTrackingBackend


class NewRelicBackend(ErrorTrackingBackend):
    """New Relic. The agent is configured by newrelic.ini or NEW_RELIC_* env vars.
    Option: browser_timing_header (render the browser agent header when auto-injection is off)."""

    sdk_module = "newrelic"
    extra = "newrelic"
    browser_template = "erp_framework/error_tracking/newrelic.html"
    start_hint = (
        "Start the process with `newrelic-admin run-program`, or call "
        "newrelic.agent.initialize() at the top of wsgi.py / asgi.py."
    )

    def agent_started(self):
        # Set by newrelic.agent.initialize(), which newrelic-admin runs when a license key or config file is set.
        try:
            import newrelic.config
        except ImportError:
            return False
        return getattr(newrelic.config, "_configuration_done", False)

    def browser_config(self, request):
        if not self.options.get("browser_timing_header"):
            return None
        try:
            import newrelic.agent
        except ImportError:
            return None
        return {"header": newrelic.agent.get_browser_timing_header()}

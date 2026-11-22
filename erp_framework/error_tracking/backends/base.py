import importlib.util

from django.core.checks import Error, Warning


class ErrorTrackingBackend:
    """One error-tracking service: server start-up, browser snippet and system checks."""

    sdk_module = ""  # Python package the backend imports, verified by check()
    extra = ""  # django-erp-framework extra that installs sdk_module
    browser_template = ""
    browser_keys = ()  # options passed to browser_template, rendered only when all browser_requires are set
    browser_requires = ()
    start_hint = ""  # set by tools whose agent starts before Django; check() then warns when it is not running

    def __init__(self, options):
        self.options = options

    def init_server(self):
        """Called once from ERPFrameworkConfig.ready()."""

    def agent_started(self):
        return True

    def browser_config(self, request):
        """Values for browser_template, or None to render no snippet."""
        if not self.browser_keys or not all(self.options.get(key) for key in self.browser_requires):
            return None
        return {key: self.options.get(key, "") for key in self.browser_keys}

    def browser_context(self, request):
        config = self.browser_config(request)
        if config is None or not self.browser_template:
            return None
        return {"template": self.browser_template, "config": config}

    def check(self):
        if self.sdk_module and importlib.util.find_spec(self.sdk_module) is None:
            return [
                Error(
                    f"Error tracking backend {type(self).__name__} needs {self.sdk_module}, which is not installed.",
                    hint=f"pip install django-erp-framework[{self.extra}]",
                    obj="ERP_FRAMEWORK_SETTINGS['error_tracking']",
                    id="erp_framework.E010",
                )
            ]
        if self.start_hint and not self.agent_started():
            return [
                Warning(
                    f"Error tracking backend {type(self).__name__}: the agent is not running in this process.",
                    hint=self.start_hint,
                    obj="ERP_FRAMEWORK_SETTINGS['error_tracking']",
                    id="erp_framework.W010",
                )
            ]
        return []

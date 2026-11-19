from django.core.checks import Error

from .base import ErrorTrackingBackend


class ExternalBackend(ErrorTrackingBackend):
    """The project starts its tool itself; the framework only renders the project's
    snippet. Options: template, config (passed to the template as `config`)."""

    def __init__(self, options):
        super().__init__(options)
        self.browser_template = options.get("template", "")

    def browser_config(self, request):
        return self.options.get("config", {})

    def check(self):
        if self.browser_template:
            return []
        return [
            Error(
                "The external error tracking backend needs a `template` option.",
                obj="ERP_FRAMEWORK_SETTINGS['error_tracking']",
                id="erp_framework.E012",
            )
        ]

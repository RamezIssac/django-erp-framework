from django.core.checks import Warning

from .base import ErrorTrackingBackend


class AgentBackend(ErrorTrackingBackend):
    """A tool whose agent starts before Django (wsgi/asgi or a wrapper command), not in ready()."""

    start_hint = ""

    def agent_started(self):
        raise NotImplementedError

    def check(self):
        errors = super().check()
        if not errors and not self.agent_started():
            errors.append(
                Warning(
                    f"Error tracking backend {type(self).__name__}: the agent is not running in this process.",
                    hint=self.start_hint,
                    obj="ERP_FRAMEWORK_SETTINGS['error_tracking']",
                    id="erp_framework.W010",
                )
            )
        return errors

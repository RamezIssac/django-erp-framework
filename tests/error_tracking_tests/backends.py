from erp_framework.error_tracking.backends.base import ErrorTrackingBackend


class RecordingBackend(ErrorTrackingBackend):
    browser_template = "error_tracking_tests/external.html"
    started_with = None

    def init_server(self):
        RecordingBackend.started_with = self.options

    def browser_config(self, request):
        return {"api_key": self.options["api_key"]}

"""Pluggable error tracking, configured by ERP_FRAMEWORK_SETTINGS["error_tracking"]."""

from django.conf import settings
from django.utils.module_loading import import_string

BUILTIN_BACKENDS = {
    "sentry": "erp_framework.error_tracking.backends.sentry.SentryBackend",
    "rollbar": "erp_framework.error_tracking.backends.rollbar.RollbarBackend",
    "newrelic": "erp_framework.error_tracking.backends.newrelic.NewRelicBackend",
    "datadog": "erp_framework.error_tracking.backends.datadog.DatadogBackend",
    "external": "erp_framework.error_tracking.backends.external.ExternalBackend",
}


def get_backend():
    """The configured backend instance, or None when error tracking is off.

    Raises ImportError when `backend` names neither a built-in nor an importable class.
    """
    config = getattr(settings, "ERP_FRAMEWORK_SETTINGS", {}).get("error_tracking") or {}
    name = config.get("backend")
    if not name:
        return None
    backend_class = import_string(BUILTIN_BACKENDS.get(name, name))
    return backend_class(config.get("options") or {})

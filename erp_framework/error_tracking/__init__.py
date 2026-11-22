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


def get_backend(fail_silently=True):
    """The configured backend instance, or None when error tracking is off.

    A `backend` that cannot be imported gives None, or ImportError (check E011) with fail_silently=False.
    """
    config = getattr(settings, "ERP_FRAMEWORK_SETTINGS", {}).get("error_tracking") or {}
    name = config.get("backend")
    if not name:
        return None
    try:
        backend_class = import_string(BUILTIN_BACKENDS.get(name, name))
    except ImportError:
        if fail_silently:
            return None
        raise
    return backend_class(config.get("options") or {})

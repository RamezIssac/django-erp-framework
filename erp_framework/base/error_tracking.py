"""Sentry/GlitchTip error tracking, configured by ERP_FRAMEWORK_SETTINGS["error_tracking"]."""

import sentry_sdk
from django.conf import settings
from sentry_sdk.integrations.logging import ignore_logger

DEFAULTS = {
    "dsn": "",
    "environment": "",
    "release": "",
    "include_local_variables": False,
}


def error_tracking_settings():
    framework_settings = getattr(settings, "ERP_FRAMEWORK_SETTINGS", {})
    return {**DEFAULTS, **framework_settings.get("error_tracking", {})}


def start_error_tracking():
    """Start sentry-sdk for errors only; return True when it was started (a DSN is set)."""
    config = error_tracking_settings()
    if not config["dsn"]:
        return False
    sentry_sdk.init(
        dsn=config["dsn"],
        environment=config["environment"] or None,
        release=config["release"] or None,
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=config["include_local_variables"],
        traces_sample_rate=0.0,
    )
    # The dev server's access log repeats every 500 as a second issue.
    ignore_logger("django.channels.server")
    return True

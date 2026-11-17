"""Optional Sentry/GlitchTip error tracking, configured from SENTRY_* environment variables."""

import os


def sentry_config():
    return {
        "SENTRY_DSN": os.environ.get("SENTRY_DSN", ""),
        "SENTRY_ENVIRONMENT": os.environ.get("SENTRY_ENVIRONMENT", ""),
        "SENTRY_RELEASE": os.environ.get("SENTRY_RELEASE", ""),
    }


def init_sentry(include_local_variables=False):
    """Start sentry-sdk for errors only; return True when it was started.

    A no-op returning False when SENTRY_DSN is empty or sentry-sdk is not installed.
    """
    config = sentry_config()
    if not config["SENTRY_DSN"]:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import ignore_logger
    except ImportError:
        return False

    sentry_sdk.init(
        dsn=config["SENTRY_DSN"],
        environment=config["SENTRY_ENVIRONMENT"] or None,
        release=config["SENTRY_RELEASE"] or None,
        send_default_pii=False,
        include_local_variables=include_local_variables,
        traces_sample_rate=0.0,
    )
    # The dev server's access log repeats every 500 as a second issue.
    ignore_logger("django.channels.server")
    return True

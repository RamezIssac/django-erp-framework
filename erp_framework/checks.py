from django.conf import settings
from django.core.checks import Error, register


@register()
def check_crequest(app_configs=None, **kwargs):
    errors = []
    if "crequest" not in settings.INSTALLED_APPS:
        errors.append(
            Error(
                "crequest app is missing",
                hint="Add `crequest` to INSTALLED_APPS",
                obj="settings",
                id="erp_framework.E003",
            )
        )
    if "crequest.middleware.CrequestMiddleware" not in settings.MIDDLEWARE:
        errors.append(
            Error(
                "crequest middleware is missing",
                hint='Add "crequest.middleware.CrequestMiddleware" to MIDDLEWARE',
                obj="settings",
                id="erp_framework.E003",
            )
        )
    return errors


@register()
def check_error_tracking(app_configs=None, **kwargs):
    from erp_framework.error_tracking import get_backend

    try:
        backend = get_backend()
    except ImportError as error:
        return [
            Error(
                f"Error tracking backend cannot be loaded: {error}",
                hint="Use sentry, rollbar, newrelic, datadog, external or a dotted path to a backend class.",
                obj="ERP_FRAMEWORK_SETTINGS['error_tracking']",
                id="erp_framework.E011",
            )
        ]
    return backend.check() if backend else []

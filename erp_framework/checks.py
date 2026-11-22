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

from django.conf import settings
from django.core.checks import Error, register, Warning
from django.utils.module_loading import import_string


@register()
def check_ra_settings(app_configs, **kwargs):
    errors = []
    if (
        "erp_framework.base.context_processors.global_info"
        not in settings.TEMPLATES[0]["OPTIONS"]["context_processors"]
    ):
        errors.append(
            Error(
                "context erp_framework.base.context_processors.global_info is missing",
                hint="add erp_framework.base.context_processors.global_info to context_processor",
                obj="settings",
                id="erp_framework.E002",
            )
        )
    return errors


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
def check_initial_settings(app_configs, **kwargs):
    errors = []
    if (
        "django.template.context_processors.i18n"
        not in settings.TEMPLATES[0]["OPTIONS"]["context_processors"]
    ):
        errors.append(
            Error(
                "django.template.context_processors.i18n is missing",
                hint='Add "django.template.context_processors.i18n" to context_processors',
                obj="settings",
                id="erp_framework.E003",
            )
        )
    if (
        "django.template.context_processors.static"
        not in settings.TEMPLATES[0]["OPTIONS"]["context_processors"]
    ):
        errors.append(
            Error(
                "django.template.context_processors.static is missing",
                hint='Add "django.template.context_processors.static" to context_processors',
                obj="settings",
                id="erp_framework.E003",
            )
        )

    return errors

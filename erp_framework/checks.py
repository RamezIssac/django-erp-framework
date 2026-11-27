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
def doc_type_effects_check(app_configs=None, **kwargs):
    from .doc_types import check_doc_type_effects, transaction_models

    models = transaction_models()
    if app_configs is not None:
        labels = {config.label for config in app_configs}
        models = [model for model in models if model._meta.app_label in labels]
    return check_doc_type_effects(models)


@register()
def movements_check(app_configs=None, **kwargs):
    from .movements import check_movements, movements_models

    models = movements_models()
    if app_configs is not None:
        labels = {config.label for config in app_configs}
        models = [model for model in models if model._meta.app_label in labels]
    return check_movements(models)

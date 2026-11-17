from erp_framework.base.error_tracking import sentry_config


def sentry(request):
    return sentry_config()

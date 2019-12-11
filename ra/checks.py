from __future__ import unicode_literals

from django.conf import settings
from django.core.checks import Error, register, Warning
from django.utils.module_loading import import_string

@register()
def check_ra_settings(app_configs, **kwargs):
    errors = []
    if 'ra.base.context_processors.global_info' not in settings.TEMPLATES[0]['OPTIONS']['context_processors']:
        errors.append(
            Error(
                'context ra.base.context_processors.global_info is missing',
                hint="add ra.base.context_processors.global_info to context_processor",
                obj='settings',
                id='RA.E002',
            )
        )
    return errors


@register()
def check_crequest(app_configs, **kwargs):
    errors = []
    if 'crequest' not in settings.INSTALLED_APPS:
        errors.append(
            Error('crequest app is missing',
                  hint='Add `crequest` to INSTALLED_APPS',
                  obj='settings',
                  id='ra.E003',
                  )
        )
    if 'crequest.middleware.CrequestMiddleware' not in settings.MIDDLEWARE:
        errors.append(
            Error('crequest middleware is missing',
                  hint='Add "crequest.middleware.CrequestMiddleware" to MIDDLEWARE',
                  obj='settings',
                  id='ra.E003',
                  )
        )
    return errors


@register()
def check_initial_settings(app_configs, **kwargs):
    errors = []
    if 'django.template.context_processors.i18n' not in settings.TEMPLATES[0]['OPTIONS']['context_processors']:
        errors.append(
            Error('django.template.context_processors.i18n is missing',
                  hint='Add "django.template.context_processors.i18n" to context_processors',
                  obj='settings',
                  id='ra.E003',
                  )
        )
    if 'django.template.context_processors.static' not in settings.TEMPLATES[0]['OPTIONS']['context_processors']:
        errors.append(
            Error('django.template.context_processors.static is missing',
                  hint='Add "django.template.context_processors.static" to context_processors',
                  obj='settings',
                  id='ra.E003',
                  )
        )

    return errors


# @register()
# todo bring back
def check_custom_error_pages(app_configs, **kwargs):
    # If there is a problem looking like a circular dependency
    # like "(project) does not define a "urls" attribute/class
    # it's probably because urls module isn't fully loaded and functinal
    # make sure to call reverse() before

    errors = []
    urls = import_string(settings.ROOT_URLCONF)
    if not hasattr(urls, 'handler500'):
        errors.append(
            Error('Custom handler500 is missing',
                  hint='Add "handler500 = ra.utils.views.server_error" to %s' % settings.ROOT_URLCONF,
                  obj='urls',
                  id='ra.E003',
                  )
        )
    if not hasattr(urls, 'handler404'):
        errors.append(
            Error('Custom handler404 is missing',
                  hint='Add "handler404 = ra.utils.views.not_found_error " to %s' % settings.ROOT_URLCONF,
                  obj='urls',
                  id='ra.E003',
                  )
        )
    return errors

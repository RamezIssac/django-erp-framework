from django.urls import reverse_lazy

from . import app_settings


def global_info(request):
    context = dict(autocomplete_base_url=reverse_lazy('ra_admin:autocomplete'))
    for i in app_settings.__dict__.keys():
        if not i.startswith('__') and i != 'settings':
            context[i] = getattr(app_settings, i)
    return context

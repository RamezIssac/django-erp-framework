from __future__ import unicode_literals

from django.utils.translation import get_language


# from erp_framework.base.helpers import admin_get_app_list


def get_each_context(request, admin_site):
    context = {}
    current_language = get_language() or ""
    cache_key = "app_list_%s_%s" % (request.user.pk, current_language)
    # cache_val = cache.get(cache_key)
    # if not cache_val or settings.DEBUG:
    #     cache_val = admin_get_app_list(request, admin_site)
    #     cache.set(cache_key, cache_val)
    # context["app_list"] = cache_val
    context["admin_site"] = admin_site
    return context

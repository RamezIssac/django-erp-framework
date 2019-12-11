from __future__ import unicode_literals

from django.template.loader import get_template

from ra.base import app_settings


class RaSuitMenu(object):

    @classmethod
    def get_menu(cls, context, request, admin_site):
        from ra.admin.templatetags.suit_menu import get_menu as suit_get_menu
        context['app_list'] = suit_get_menu(context, request)
        return get_template('%s/menu.html' % app_settings.RA_THEME).render(context.flatten())


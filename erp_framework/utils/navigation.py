from __future__ import unicode_literals

from django.template.loader import get_template

from erp_framework.base import app_settings


class RaSuitMenu(object):
    @classmethod
    def get_menu(cls, context, request, admin_site):
        from erp_framework.admin.templatetags.suit_menu import get_menu as suit_get_menu

        context["app_list"] = suit_get_menu(context, request)
        return get_template("ra/menu.html").render(context.flatten())

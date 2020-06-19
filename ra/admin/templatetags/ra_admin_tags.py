from __future__ import unicode_literals

from django import template
from django.contrib.admin.templatetags.admin_list import result_headers, result_hidden_fields, results
from django.template import loader
from django.template.loader import get_template
from django.urls import reverse
from django.utils.module_loading import import_string
from django.utils.safestring import mark_safe

from ra.base import app_settings

register = template.Library()


@register.simple_tag(takes_context=True)
def render_navigation_menu(context):
    navigation_class = import_string(app_settings.RA_NAVIGATION_CLASS)
    request = context['request']
    admin_site = context['admin_site']
    return mark_safe(navigation_class.get_menu(context, request, admin_site))


@register.simple_tag(takes_context=True)
def render_reports_menu(context):
    request = context['request']
    is_in_reports = False
    active_base_model = ''
    if request.path.startswith('/reports/'):
        is_in_reports = True
        active_base_model = [x for x in request.path.split('/') if x][1]

    from ra.reporting.registry import report_registry
    classes = report_registry.get_base_models()
    if classes:
        t = get_template(f'ra/reports_menu.html')
        return mark_safe(
            t.render({'classes': classes, 'is_in_reports': is_in_reports, 'active_base_model': active_base_model}))
    return ''


@register.simple_tag(takes_context=True)
def get_report(context, base_model, report_slug):
    from ra.reporting.registry import report_registry
    return report_registry.get(namespace=base_model, report_slug=report_slug)

from django import template
from django.template.loader import get_template
from django.utils.functional import Promise
from django.utils.safestring import mark_safe
from logging import getLogger

logger = getLogger(__name__)

from erp_framework.utils.permissions import has_report_permission_permission

register = template.Library()

# def is_time_series(report, obj_instance, pk_name):
#     return report.get('time_series_pattern', '')

# @register.simple_tag(takes_context=True)
# def can_print_report(context, report):
#     return has_report_permission_permission(
#         context["request"], report.get_base_model_name(), report.get_report_slug()
#     )

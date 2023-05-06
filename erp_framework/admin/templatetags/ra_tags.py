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


from django.core.serializers import serialize
from django.db.models.query import QuerySet
import simplejson as json


def jsonify(object):
    def date_handler(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        elif isinstance(obj, Promise):
            return str(obj)

    if isinstance(object, QuerySet):
        return serialize("json", object)

    return mark_safe(json.dumps(object, use_decimal=True, default=date_handler))


register.filter("jsonify", jsonify)


@register.simple_tag(takes_context=True)
def can_print_report(context, report):
    return has_report_permission_permission(
        context["request"], report.get_base_model_name(), report.get_report_slug()
    )


@register.filter
def addstr(arg1, arg2):
    """concatenate arg1 & arg2"""
    return str(arg1) + str(arg2)


@register.simple_tag
def get_html_panel(report, template="", **kwargs):
    kwargs["report"] = report
    if not report:
        raise ValueError(
            "report argument is empty. Are you sure you're using the correct report name"
        )

    # No chart argument default to True if no charts in reports
    kwargs.setdefault("no_chart", not bool(report.chart_settings))

    template = get_template(template or "erp_framework/report_widget_template.html")
    return template.render(context=kwargs)

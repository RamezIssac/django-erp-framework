from django import template
from django.urls import reverse
from django.utils.encoding import force_text
from django.utils.functional import Promise
from django.utils.safestring import mark_safe

from ra.base.app_settings import RA_APP_ICONS

register = template.Library()

from logging import getLogger

logger = getLogger(__name__)


@register.simple_tag
def get_typed_report_url_param(widget_instance, obj_instance, pk_name=None, append_ajax=True):
    pk_name = pk_name or ''
    if obj_instance:
        pk_name = pk_name or obj_instance.get_pk_name()
    default_param = '?&ajax=true'  # &from_doc_date=2014-01-01%2000:00:00
    namespace = widget_instance['namespace'] if type(widget_instance) is dict else widget_instance.get_base_model_name()
    report_slug = widget_instance['report_slug'] if type(widget_instance) is dict else widget_instance.get_report_slug()
    url = reverse('admin:report_list', args=(namespace,))
    url += '%s/' % report_slug

    report_settings = widget_instance['form_settings'] if type(
        widget_instance) is dict else widget_instance.form_settings
    report_settings = report_settings or {}
    report_matrix = report_settings.get('matrix', False)
    report_matrix_show_other = report_settings.get('matrix_show_other', True)
    report_group_by = report_settings.get('group_by', '')

    if report_group_by != pk_name[:-3] or not (obj_instance and pk_name):
        default_param += '&get_group=true'
    if obj_instance and pk_name:  # False in case of Home Page
        if report_matrix == '-' or report_matrix == '' or not report_matrix:
            default_param += '&%s=%s' % (pk_name, str(obj_instance.pk))
        else:
            default_param += '&matrix_entities=%s' % obj_instance.pk
            if report_matrix_show_other:
                default_param += '&matrix_show_other=on'
    default_param = url + default_param
    return mark_safe(default_param)


def is_time_series(report, obj_instance, pk_name):
    return report.get('time_series_pattern', '')


from django.core.serializers import serialize
from django.db.models.query import QuerySet
import simplejson as json


def jsonify(object):
    def date_handler(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        elif isinstance(obj, Promise):
            return force_text(obj)
        # else:
        #     raise TypeError(
        #         "Unserializable object {} of type {}".format(obj, type(obj))
        #     )

    if isinstance(object, QuerySet):
        return serialize('json', object)

    return mark_safe(json.dumps(object, use_decimal=True, default=date_handler))


register.filter('jsonify', jsonify)


@register.filter
def subtract(value, arg):
    return value - arg


panel_format = """<div class="panel panel-default">
								<div class="panel-heading">
									<i class="clip-stats"></i>
									%(panel_title)s
									<div class="panel-tools">
										<a class="btn btn-xs btn-link panel-collapse collapses" href="#">
										</a>
										%(panel_options)s

									</div>
								</div>
								<div class="panel-body">
									%(body)s
								</div>
							</div>
"""


@register.simple_tag
def get_app_icon(app):
    icon = RA_APP_ICONS.get(app['app_label'], '')
    if icon:
        icon = '<i class="%s"></i>' % icon
    else:
        icon = '<i class="icon-make-group position-left"></i>'
    return mark_safe(icon)


@register.filter
def translate_change_message(message):
    from ra.activity.admin import translate_change_message
    return translate_change_message(message)

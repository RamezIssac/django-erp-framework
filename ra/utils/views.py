import copy
import re

from django.shortcuts import render
from django.urls import reverse, NoReverseMatch
from django.utils.encoding import force_text
from django.utils.translation import get_language_bidi

from ra.base import app_settings

easter_western_map = {1776: 48,  # 0
                      1777: 49,  # 1
                      1778: 50,  # 2
                      1779: 51,  # 3
                      1780: 52,  # 4
                      1781: 53,  # 5
                      1782: 54,  # 6
                      1783: 55,  # 7
                      1784: 56,  # 8
                      1785: 57,  # 9
                      # another ord
                      1632: 48,  # 0
                      1633: 49,  # 1
                      1634: 50,  # 2
                      1635: 51,  # 3
                      1636: 52,  # 4
                      1637: 53,  # 5
                      1638: 54,  # 6
                      1639: 55,  # 7
                      1640: 56,  # 8
                      1641: 57,  # 9
                      }  # 9

re_time_series = re.compile('TS\d+')

DEFAULT_PRINT = app_settings.RA_PRINT_SETTINGS
DEFAULT_PRINT_BIDI = app_settings.RA_PRINT_SETTINGS_RTL


def get_linkable_slug_title(model_name, pk, field_value, target_blank=False):
    return_val = field_value
    # import pdb; pdb.set_trace()
    from ra.admin.admin import ra_admin_site

    model_map = ra_admin_site.get_admin_by_model_name(model_name)
    target_blank = 'target="_blank"' if target_blank else ''
    # search_in = MODELS
    if model_map:
        # try:
        model = model_map['model']
        if model_map['admin'].enable_view_view:
            redirect_url = reverse(
                '%s:%s_%s_view' % (app_settings.RA_ADMIN_SITE_NAME, model._meta.app_label, model._meta.model_name),
                args=(pk,))
        else:
            redirect_url = reverse(
                '%s:%s_%s_change' % (app_settings.RA_ADMIN_SITE_NAME, model._meta.app_label, model._meta.model_name),
                args=(pk,))
        if redirect_url:
            return_val = '<a class="decoratedLink" data-pk="%s" href="%s" %s>%s</a>' % (
                pk, redirect_url, target_blank, field_value)
        else:
            return_val = field_value

    return return_val


def get_decorated_slug(field_name, field_value, obj, dict_format=True, new_page=False,
                       use_push_state=False, *args,
                       **kwargs):
    from ra.base.registry import get_model_settings, get_doc_type_settings
    models = get_model_settings()
    doc_types = get_doc_type_settings()

    return_val = ''
    if field_name == 'slug':
        if dict_format:
            model = obj['doc_type']
        else:
            model = obj.doc_type
        search_in = doc_types
    else:
        model = field_name.split('__')[0]
        search_in = models
    target_blank = 'target="_blank"' if new_page else ''
    onclick = 'onclick="use_push_state()"' if use_push_state else ''
    if model in search_in:
        func = search_in[model].get('redirect_url_prefix_func', None)
        if func:
            redirect_url = func(field_name, field_value, obj)
        else:
            redirect_url = search_in[model].get('redirect_url_prefix', '')
        try:
            redirect_url = force_text(redirect_url)
        except NoReverseMatch:
            return field_value

        if redirect_url:
            if search_in == doc_types:
                redirect_url += 'slug/%s/' % field_value
            else:
                redirect_url += field_value + '/'
            return_val = '<a href="%s"  %s %s >%s</a>' % (redirect_url, target_blank, onclick, field_value)
        else:
            return_val = field_value

    return return_val


def get_print_settings():
    '''
    Get the print_settings while taking BIDI into account
    :return: default appropriate print settings
    '''
    default_print_settings = copy.deepcopy(DEFAULT_PRINT)
    if get_language_bidi():
        default_print_settings.update(copy.deepcopy(DEFAULT_PRINT_BIDI))
    return default_print_settings


def get_typed_reports_map(typed_reports, only_report_slug=None):
    """
    # todo revise
    :param typed_reports:
    :param only_report_slug:
    :return:
    """
    reports = typed_reports

    reports_map = {
        'slugs': [],
        'reports': [],
    }

    for report in reports:
        view = report
        if not only_report_slug or only_report_slug == view.get_report_slug():
            if True:  # user.has_perm(view_perm):
                reports_map['slugs'].append(view.get_report_slug())
                reports_map['reports'].append(view)
    return reports_map


def apply_order_to_typed_reports(lst, order_list):
    values = []
    unordered = list(lst)
    for o in order_list:
        for x in unordered:
            if x.get_report_slug() == o:
                values.append(x)
                unordered.remove(x)
    values += unordered
    return values


def get_typed_reports_for_templates(model_name, user=None, request=None, only_report_slug=None, load_func=None):
    from ra.reporting.registry import report_registry

    load_func = load_func or report_registry.get_report_classes_by_namespace
    reports = load_func(model_name)
    report_list = []
    user_reports = request.session.get('user_reports', [])
    for report in reports:
        view = report
        if not only_report_slug or only_report_slug == view.get_report_slug():

            view_perm = '%s.%s_view' % (view.get_base_model_name(), view.get_report_slug())
            if view_perm in user_reports or user.is_superuser:
                report_list.append(view)

    return report_list


def access_denied(request):
    return render(request, template_name='ra/access_denied.html')


def server_error(request, template_name='500.html'):
    """
    500 error handler.

    Templates: :template:`500.html`
    Context: None
    """
    response = render(request, '500.html', {})
    response.status_code = 500
    return response


def not_found_error(request, template_name='404.html'):
    """
    500 error handler.

    Templates: :template:`500.html`
    Context: None
    """
    response = render(request, '404.html', {})
    response.status_code = 404
    return response

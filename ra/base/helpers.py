from __future__ import unicode_literals

import logging
import time
from collections import OrderedDict

from django.apps import apps
from django.db import connection
from django.template.defaultfilters import capfirst
from django.urls import reverse, NoReverseMatch
from django.utils.encoding import force_text

logger = logging.getLogger(__name__)

get_model = apps.get_model


def get_obj_from_list(lst, key, val):
    return get_from_list(False, lst, key, val)


def get_from_list(by_getattr, lst, attr_name, val):
    """
    Gets an object from the supplied list by `getattr` or by `__item__`
    :param by_getattr: Use getattr, if False we use __item__ (dict access)
    :param lst: list of the objects
    :param attr_name: Or Key
    :param val: value we search for
    :return: The Item if found else return False
    """

    def get_by_key(_dict, _key):
        return _dict[_key]

    if by_getattr:
        lookup = getattr
    else:
        lookup = get_by_key
    for l in lst:
        if lookup(l, attr_name) == val:
            return l
    return False


class RaPermissionWidgetExclude(object):
    def __call__(self, model):
        from ra.base.models import BaseMovementItemInfo, BaseReportModel

        if BaseMovementItemInfo in model.__mro__ or BaseReportModel in model.__mro__ or model._meta.managed is False:
            return True
        if model._meta.auto_created:
            return True
        return False


def order_apps(app_list):
    """ Called in admin/base_site.html template override and applies custom ordering of
        apps/models defined by settings.ADMIN_REORDER
    """
    from . import app_settings
    # sort key function - use index of item in order if exists, otherwise item
    sort = lambda order, item: (order.index(item), "") if item in order else (len(order), item)

    # sort the app list
    order = OrderedDict(app_settings.ADMIN_REORDER)
    app_list.sort(key=lambda app: sort(order.keys(), app["app_url"].strip("/").split("/")[-1]))
    for i, app in enumerate(app_list):
        # sort the model list for each app
        app_name = app["app_url"].strip("/").split("/")[-1]
        model_order = [m.lower() for m in order.get(app_name, [])]
        app_list[i]["models"].sort(
            key=lambda model: sort(model_order, model.get("admin_url", '').strip("/").split("/")[-1]))
    return app_list


def admin_get_app_list(request, admin_site):
    """
    :param request: Copied from AdminSite.index() djagno v1.8
    :param admin_site:
    :return:
    """
    from ra.base.app_settings import RA_MENU_HIDE_MODELS, RA_ADMIN_SITE_NAME
    app_dict = {}
    for model, model_admin in admin_site._registry.items():
        app_label = model._meta.app_label
        has_module_perms = model_admin.has_module_permission(request)

        is_model_hidden = '%s_%s' % (app_label, model.__name__.lower()) in RA_MENU_HIDE_MODELS

        if has_module_perms and not is_model_hidden:
            perms = model_admin.get_model_perms(request)

            # Check whether user has any perm for this module.
            # If so, add the module to the model_list.
            if True in perms.values():
                info = (RA_ADMIN_SITE_NAME, app_label, model._meta.model_name)
                model_dict = {
                    'name': capfirst(model._meta.verbose_name_plural),
                    'object_name': model._meta.object_name,
                    'perms': perms,
                    'model_class': model,
                }
                if perms.get('view', False) or perms.get('change', False) or perms.get('add', False):
                    try:
                        model_dict['admin_url'] = reverse('%s:%s_%s_changelist' % info, current_app=admin_site.name)
                    except NoReverseMatch:
                        pass
                if perms.get('add', False):
                    try:
                        model_dict['add_url'] = reverse('%s:%s_%s_add' % info, current_app=admin_site.name)
                    except NoReverseMatch:
                        pass
                if app_label in app_dict:
                    app_dict[app_label]['models'].append(model_dict)
                else:
                    app_dict[app_label] = {
                        'name': apps.get_app_config(app_label).verbose_name,
                        'app_label': app_label,
                        'app_url': reverse(
                            '%s:app_list' % RA_ADMIN_SITE_NAME,
                            kwargs={'app_label': app_label},
                            current_app=admin_site.name,
                        ),
                        'has_module_perms': has_module_perms,
                        'models': [model_dict],
                    }

    # Sort the apps alphabetically.
    app_list = list(app_dict.values())
    app_list.sort(key=lambda x: x['name'].lower())

    # Sort the models alphabetically within each app.
    for app in app_list:
        app['models'].sort(key=lambda x: x['name'])

    return order_apps(app_list)


def dictsort(value, arg, desc=False):
    """
    Takes a list of dicts, returns that list sorted by the property given in
    the argument.
    """
    return sorted(value, key=lambda x: x[arg], reverse=desc)


def get_ra_relevant_content_types():
    """
    This method scans the content type and show only what relevant based on the the exclude function supplied to
    tabular_permissions
    #todo make a separate function that might fall back to tabular_permissions
    :return:
    """
    from django.contrib.contenttypes.models import ContentType
    from ra.base.models import BaseReportModel
    from tabular_permissions.app_settings import EXCLUDE_FUNCTION

    relevant_ct = []
    cs = ContentType.objects.all()
    exclude_function = EXCLUDE_FUNCTION
    for c in cs:
        model = c.model_class()
        if not model:
            continue
        if BaseReportModel in model.__mro__:
            continue
        if model:
            if not exclude_function(model):
                relevant_ct.append((c.pk, force_text(model._meta.verbose_name_plural)))

    return relevant_ct


def get_next_serial(model):
    """
    Get the next serial to put in the slug based on the maximum slug found + 1
    :param model: the model to get the next serial for
    :return: a string
    """
    try:
        doc_type = model.get_doc_type()
    except:
        doc_type = False

    if model._meta.parents.values():
        # This is an inherited model, look in the parent
        parent = model._meta.parents.keys()[-1]
        table_name = parent._meta.db_table
    else:
        table_name = model._meta.db_table

    cursor = connection.cursor()
    try:
        statment = "select max((slug::text)::DOUBLE PRECISION) from %s where slug ~'^\d+$'" % table_name
        if doc_type:
            statment += " and doc_type='%s'" % doc_type

        cursor.execute(statment)
        row = cursor.fetchone()
        max_slug = row[0]
        if max_slug:
            try:
                max_slug = str(int(max_slug) + 1)
            except ValueError:
                max_slug = ''
        else:
            max_slug = '1'
        return max_slug
    except Exception as e:
        raise e
        logger.error(e)
        return repr(time.time()).replace('.', '')


def default_formfield_for_dbfield(model_admin, db_field, form_field, request, **kwargs):
    """
    A system wide hook to change how db_field are displayed as formfields
    :param model_admin: the ModelAdmin instance
    :param db_field: db_field
    :param form_field: the default form_field
    :param request: the request
    :return: form_field used
    """
    return form_field

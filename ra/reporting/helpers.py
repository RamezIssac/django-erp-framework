import logging

from crispy_forms.layout import Column, Field, Row, Div, Layout
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import ugettext_lazy as _

from ra.base import app_settings
from ra.base.models import BaseMovementInfo
from ra.reporting.crispy_layouts import StackedField2

get_model = apps.get_model

User = settings.AUTH_USER_MODEL

logger = logging.getLogger(__name__)
# from django.utils.translation import ugettext_lazy as _

GROUP_BY_PREFIX = 'group_by'
DISPLAY_PREFIX = 'details_columns'
AGGREGATE_ON__PREFIX = 'aggregate_on'
USE_SLUG = False

DECIMAL_FIELDS = ['value', '__debit__', '__credit__', '__fb__', '__balance__', '__total__', 'quantity', 'price',
                  'discount', '__gross_value__', '__tax_addition__', '__tax_substract__', '__doc_value__']
QUAN_DECIMAL_FIELDS = ['quan', '__debit_quan__', '__credit_quan__', '__fb_quan__', '__balance_quan__', '__total_quan__']
INT_FIELDS = ['__doc_count__', '__line_cont__']
DATE_FIELDS = ['doc_date', 'lastmod', 'creation_date']
DATETIME_DISPLAY_FORMAT = app_settings.RA_DATETIME_DISPLAY_FORMAT
DATETIME_SAVE_FORMAT = app_settings.RA_DATETIME_SAVE_FORMAT
DEFAULT_FROM_DATE_TIME = app_settings.DEFAULT_FROM_DATE_TIME

from ra.base import loading

MOVEMENT_BASE_MODELS = []


def get_model_fields2(model, use_id=True, fkeys_only=False, decimal_fields_only=False,
                      all_fields=False,
                      exclude_fields=None, exclude_models=None, no_implicit=False, appened_model_name=False,
                      no_recurse=False, recurse_name_only=False, recurse_name_slug_only=False, get_id_and_slug=False,
                      use_slug=False,
                      exclude_movement=False):
    '''
    Loop in model fields in return them in a list with various options
    @param model:
    @param fkeys_only:
    @param decimal_fields_only:
    @param all_fields:
    @param exclude_fields:
    @param exclude_models:
    @param no_implicit:
    @param appened_model_name:
    @param no_recurse:
    @param recurse_name_only:
    @param recurse_name_slug_only:
    @param use_slug:
    @param exclude_movement:
    @return:
    '''

    if use_slug is None: use_slug = USE_SLUG
    if not exclude_fields: exclude_fields = []
    if not exclude_models: exclude_models = []

    if not no_implicit: exclude_fields.append('id')
    if not no_implicit: exclude_models.append('user')
    QuanValueMovementItem = loading.get_quanvaluemovementitem_model()
    fkeys = []
    _model = None

    if type(model) is str:
        _model = get_model(*model.split('.'))
    elif type(model) is models.base.ModelBase:
        _model = model
    else:
        raise NotImplemented

    for field in _model._meta.fields:
        field_name = field.attname if not appened_model_name else _model.__name__.lower() + '__' + field.attname

        if type(field) is models.ForeignKey:

            to_model = field.remote_field.model

            to_model_name = to_model.__name__.lower()
            if exclude_movement and (BaseMovementInfo in to_model.__mro__ or QuanValueMovementItem in to_model.__mro__):
                exclude_models.append(to_model_name)

            if to_model_name not in exclude_models:

                if recurse_name_slug_only:
                    fkeys.append(to_model_name + '__slug')
                    fkeys.append(to_model_name + '__title')
                elif get_id_and_slug:
                    fkeys.append(to_model_name + '_id')
                    fkeys.append(to_model_name + '__title')

                elif use_slug:
                    fkeys.append(to_model_name + '__slug')
                elif use_id:
                    fkeys.append(to_model_name + '_id')

                elif 'movement' in to_model_name:
                    fkeys.append(to_model_name + '_id')

                elif fkeys_only or no_recurse:
                    if use_slug:
                        fkeys.append(to_model_name + '__slug')
                    else:
                        fkeys.append(field_name)

                else:
                    fkeys += get_model_fields2(field.remote_field.model, all_fields=True,
                                               exclude_fields=['notes', 'fb'],
                                               appened_model_name=True, recurse_name_only=True)
                    exclude_models.append(field.remote_field.model.__name__.lower())

        elif type(field) in (
                models.DecimalField, models.PositiveIntegerField) and not fkeys_only and not recurse_name_only:
            fkeys.append(field_name)
        else:
            if all_fields and field_name not in exclude_fields:
                if recurse_name_only:
                    if field.attname == 'title':
                        fkeys.append(field_name)
                else:
                    fkeys.append(field_name)
    return fkeys


def choices_from_list(lst, append_none=True, extra_list=None, order_list=None):
    extra_list = extra_list or []
    lst = lst + extra_list
    if order_list is not None:
        lst = apply_order_to_list(lst, order_list)

    _displayFields = ()
    for f in lst:
        if '__doc_type_' in f:
            translate = f  # extract_verbose_doc_type(f)
        else:
            translate = f
        x = ((f, _(translate)),)
        _displayFields = _displayFields + x

    if append_none:
        _displayFields = (('', '----'),) + _displayFields

    # if extra_list is not None:
    # for item in extra_list:
    # x = ((item, _(item)),)
    # _displayFields = _displayFields + x

    return _displayFields


def get_calculation_annotation(calculation_field, calculation_method):
    '''
    Returns the default django annotation
    @param calculation_field: the field to calculate ex 'value'
    @param calculation_method: the aggregation method ex: Sum
    @return: the annotation ex value__sum
    '''

    return '__'.join([calculation_field.lower(), calculation_method.name.lower()])


def apply_order_to_list(lst, order_list):
    values = []
    unordered = list(lst)
    for o in order_list:
        o = o.strip()
        if o in lst:
            values.append(o)
            try:
                unordered.remove(o)
            except ValueError:
                pass
    values += unordered
    return values


def get_foreign_keys(model):
    User_model = get_user_model()
    fields = model._meta.get_fields()
    fkeys = {}
    for f in fields:
        if f.is_relation and f.related_model is not User_model and type(f) is not models.OneToOneRel:
            fkeys[f.attname] = f
    return fkeys


def get_user_formLayout(_fkeys, report_settings, form_inst):
    layout = Layout(
        # PanelContainer(
        # #     Div(
        #         _('filters'),
        Div(
            # Div(StackedField('doc_date'), css_class='col-sm-3'),
            Div(StackedField2('from_doc_date', css_class='form-control dateinput'), css_class='col-sm-6'),
            Div(StackedField2('to_doc_date', css_class='form-control dateinput'), css_class='col-sm-6'),

            css_class='row raReportDateRange'),
        Div(css_class="mt-20", style='margin-top:20px')
    )

    # We add foreign keys to 3rd item in the layout object (count top level only) , which is the
    # fieldset containing doc_date , from_doc_date & to_doc_date
    entry_point = layout.fields[1]
    if report_settings.get('can_edit_matrix_entities', False):
        if hasattr(form_inst, 'cleaned_data'):
            if form_inst.cleaned_data['matrix'] != '':
                entry_point.append(Row(
                    Div('matrix_entities', css_class='col-sm-9'),
                    Div('matrix_show_other', css_class='col-sm-3')
                    , css_class='matrixField')
                )

    for k in _fkeys:
        # if k[:-3] in report_settings['fkey_visibility'] and k[:-3] != report_settings['matrix']:
        if k[:-3] != report_settings['matrix']:
            entry_point.append(Field(k))

    if report_settings.get('can_edit_primary_index', False):
        layout.append(Column(Field('group_by'), css_class='col-sm-3'))
    if report_settings.get('can_edit_secondary_index', False):
        layout.append(Column(Field('aggregate_on'), css_class='col-sm-3'))
    if report_settings.get('can_edit_time_series_pattern', False):
        layout.append(Column(Field('group_time_series_pattern'), css_class='col-sm-3'))
    if report_settings.get('can_edit_doc_types', False):
        layout.append(Column(Field('doc_types'), css_class='col-sm-3'))

    return layout

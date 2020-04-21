import logging
from collections import OrderedDict

from django.apps import apps
from django.conf import settings
from django.db import models

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

MOVEMENT_BASE_MODELS = []





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
    fields = model._meta.get_fields()
    fkeys = OrderedDict()
    for f in fields:
        if f.is_relation and type(f) is not models.OneToOneRel \
                and type(f) is not models.ManyToOneRel and type(f) is not models.ManyToManyRel:
            fkeys[f.attname] = f

    return fkeys


# def get_user_formLayout(_fkeys, report_settings, form_inst):
#     layout = Layout(
#         # PanelContainer(
#         # #     Div(
#         #         _('filters'),
#         Div(
#             # Div(StackedField('doc_date'), css_class='col-sm-3'),
#             Div(StackedField2('from_doc_date', css_class='form-control dateinput'), css_class='col-sm-6'),
#             Div(StackedField2('to_doc_date', css_class='form-control dateinput'), css_class='col-sm-6'),
#
#             css_class='row raReportDateRange'),
#         Div(css_class="mt-20", style='margin-top:20px')
#     )
#
#     # We add foreign keys to 3rd item in the layout object (count top level only) , which is the
#     # fieldset containing doc_date , from_doc_date & to_doc_date
#     entry_point = layout.fields[1]
#     if report_settings.get('can_edit_matrix_entities', False):
#         if hasattr(form_inst, 'cleaned_data'):
#             if form_inst.cleaned_data['matrix'] != '':
#                 entry_point.append(Row(
#                     Div('matrix_entities', css_class='col-sm-9'),
#                     Div('matrix_show_other', css_class='col-sm-3')
#                     , css_class='matrixField')
#                 )
#
#     for k in _fkeys:
#         # if k[:-3] in report_settings['fkey_visibility'] and k[:-3] != report_settings['matrix']:
#         if k[:-3] != report_settings['matrix']:
#             entry_point.append(Field(k))
#
#     if report_settings.get('can_edit_primary_index', False):
#         layout.append(Column(Field('group_by'), css_class='col-sm-3'))
#     if report_settings.get('can_edit_secondary_index', False):
#         layout.append(Column(Field('aggregate_on'), css_class='col-sm-3'))
#     if report_settings.get('can_edit_time_series_pattern', False):
#         layout.append(Column(Field('group_time_series_pattern'), css_class='col-sm-3'))
#     if report_settings.get('can_edit_doc_types', False):
#         layout.append(Column(Field('doc_types'), css_class='col-sm-3'))
#
#     return layout


def get_field_from_query_text(path, model):
    relations = path.split('__')
    _rel = model
    field = None
    for i, m in enumerate(relations):
        field = _rel._meta.get_field(m)
        if i == len(relations) -1:
            return field
        _rel = field.related_model
    return field


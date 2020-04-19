# from __future__ import unicode_literals
"""
    WIP
"""
import datetime
from collections import OrderedDict

import pytz
from crispy_forms.helper import FormHelper
from dateutil.relativedelta import relativedelta
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import MultipleChoiceField
from django.http import QueryDict
from django.utils.text import capfirst
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy

from ra.base import app_settings
from ra.base.widgets import RaBootstrapDateTime
from ra.reporting.form_fields import RaDateDateTimeField, RaAutocompleteSelectMultiple
from ra.reporting.helpers import choices_from_list, get_model_fields2, apply_order_to_list, get_foreign_keys, \
    get_user_formLayout
from ra.reporting.registry import field_registry
from ra.utils.translation import ugettext as _
from ra.admin.admin import ra_admin_site


class BaseReportForm(object):
    '''
    Holds basic function
    '''
    # date_field_name = 'doc_date'
    date_field_name = 'order__date_placed'
    support_doc_type = False

    def get_fk_filters(self):
        """
        Get the foreign key filters for report queryset,
        :return: a dicttionary of filters to be used with QuerySet.filter(**returned_value)
        """
        # todo: implement cross tab support
        _values = {}
        if self.is_valid():
            for key, field in self.foreign_keys.items():
                if key in self.cleaned_data:
                    val = self.cleaned_data[key]
                    if val:
                        val = [x for x in val.values_list('pk', flat=True)]
                        _values['%s__in' % key] = val
            return _values

    def get_date_filters(self):
        return {
            f'{self.date_field_name}__gt': self.cleaned_data['from_doc_date'],
            f'{self.date_field_name}__lte': self.cleaned_data['to_doc_date']
        }

    def get_doc_types_filters(self):
        _values = {}
        if 'doc_types' in self.cleaned_data:
            docs = []
            for e in self.cleaned_data['doc_types']:
                docs.append(e)  # (extract_verbose_doc_type(e))
            _values['doc_type__in'] = docs
        return _values

    def get_doc_type_plus_minus_lists(self):
        if self.support_doc_type:
            return self.base_model.get_doc_type_plus_list(), self.base_model.get_doc_type_minus_list()
        return [], []

    # End of new methods Ra 2

    def get_queryset_filters(self, w_date=False, w_doc_types=True):
        filters = {}
        if self.is_valid():
            filters = self.get_fk_filters()
            if w_date:
                filters.update(self.get_date_filters())

            if w_doc_types:
                filters.update(self.get_doc_types_filters())

        return filters

    def get_datatable_columns(self, get_group=False, appened_fkeys=False, wTimeSeries=True, wMatrix=True):
        _values = []
        if self.is_valid():
            if get_group:
                _values = self.get_group_by_display()

            if self.is_time_series(get_group) and wTimeSeries:
                time_series_columns = self.get_time_series_columns(get_group)
                _values += time_series_columns

            if self.is_matrix_support(get_group) and wMatrix:
                matrix_columns = self.get_matrix_fields()
                _values += matrix_columns
            return _values

        return _values

    def get_group_by_filters(self):
        if self.is_valid():
            return self.cleaned_data['group_by']
        return None

    def __init__(self, *args, support_doc_type=False, **kwargs):
        self.support_doc_type = support_doc_type
        saved_report_meta = kwargs.pop('form_settings', {})
        imposed_form_settings = kwargs.pop('imposed_form_settings', False)
        if imposed_form_settings and saved_report_meta:
            initial_settings = self.initial_settings.copy()
            initial_settings.update(saved_report_meta)
            saved_report_meta = initial_settings

        kwargs.pop('admin_state', False)
        data = QueryDict('', mutable=True)
        if 'data' in kwargs:

            data = kwargs.get('data', {}).copy()
            if '__doc_typeid__' in data:
                # inject __doc_typeid__
                # in place of doc_types to get the criteria in place like a boss
                doc_type_id = data.pop('__doc_typeid__')
                doc_type_id = '__doc_type_%s__' % doc_type_id[0]
                data.pop('doc_types', False)
                data.setlist('doc_types', [u'%s' % doc_type_id])

        if saved_report_meta:
            enforce = False
            for field in self.base_fields.keys():
                if field in saved_report_meta:
                    if type(self.base_fields[field]) in [forms.MultipleChoiceField,
                                                         EasyMultipleChoiceField] and not field == 'doc_types':
                        data.setlist(field, saved_report_meta[field] or [])
                    elif field in ['from_doc_date']:  # , 'to_doc_date']:

                        if hasattr(saved_report_meta[field], '_proxy____cast'):
                            _date = saved_report_meta[field]._proxy____cast()
                        elif type(saved_report_meta[field]) is datetime.datetime:
                            _date = saved_report_meta[field]
                        else:
                            _date = datetime.datetime.strptime(saved_report_meta[field], '%Y-%m-%d %H:%M:%S')
                            # _date = saved_report_meta[field].strptime(saved_report_meta[field],'%Y-%m-%d %H:%M:%S')
                        if 'from_doc_date_0' not in data:
                            data['from_doc_date_0'] = _date.date()

                        if 'from_doc_date_1' not in data:
                            data['from_doc_date_1'] = _date.time().strftime('%H:%M')

                    elif field in ['to_doc_date']:
                        _date = saved_report_meta[field]
                        if 'to_doc_date_0' not in data:
                            data['to_doc_date_0'] = _date.date() + + datetime.timedelta(days=1)

                        if 'to_doc_date_1' not in data:
                            data['to_doc_date_1'] = datetime.time.min.strftime('%H:%M')

                    elif field == 'group_by':
                        if not saved_report_meta.get('can_edit_primary_index', False) or u'group_by' not in data:
                            data[field] = saved_report_meta[field]

                    elif field == 'aggregate_on':
                        if not saved_report_meta.get('can_edit_secondary_index',
                                                     False) or u'aggregate_on' not in data:
                            data[field] = saved_report_meta[field]

                    elif field == 'time_series_pattern':
                        if not saved_report_meta.get('can_edit_time_series_pattern',
                                                     False) or u'time_series_pattern' not in data:
                            data[field] = saved_report_meta[field]
                    elif field == 'matrix_show_other':
                        data[field] = saved_report_meta[field]
                    elif field == 'matrix_entities':
                        pass
                    elif field == 'doc_types':
                        if not saved_report_meta.get('can_edit_doc_types',
                                                     False) or u'doc_types' not in data:
                            data.setlist(field, saved_report_meta[field])



                    else:

                        if field not in self.foreign_keys.keys():
                            data[field] = saved_report_meta[field]

        if data:
            kwargs['data'] = data
        if data['matrix']:
            from ra.admin.admin import ra_admin_site
            matrix_field = self.foreign_keys[data['matrix'] + '_id']
            formfield = matrix_field.formfield(
                **{'form_class': forms.ModelMultipleChoiceField,
                   'required': False,
                   'widget': RaAutocompleteSelectMultiple(matrix_field.remote_field, ra_admin_site,
                                                          attrs={'class': 'select2bs4'})})
            self.base_fields['matrix_entities'] = formfield

        super(BaseReportForm, self).__init__(*args, **kwargs)
        self.is_valid()

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-2 col-md-2 col-lg-1'
        self.helper.field_class = 'col-sm-10 col-md-10 col-lg-11'
        self.helper.form_tag = True

        self.helper.layout = get_user_formLayout(self._fkeys, saved_report_meta, self)

    def get_from_doc_date(self):
        doc_date = self.cleaned_data['doc_date']
        try:
            doc_date = doc_date.strftime('%Y-%m-%d')
        except:
            doc_date = None

        if doc_date:
            date_1 = pytz.utc.localize(
                datetime.datetime.combine(self.cleaned_data['doc_date'], datetime.datetime.min.time()))
            date_2 = date_1 + datetime.timedelta(days=1)
            self.cleaned_data['from_doc_date'] = date_1
            self.cleaned_data['to_doc_date'] = date_2
        return self.cleaned_data['from_doc_date'] if self.cleaned_data[
            'from_doc_date'] else app_settings.RA_DEFAULT_FROM_DATETIME

    def get_to_doc_date(self):
        return self.cleaned_data['to_doc_date'] if self.cleaned_data['to_doc_date'] else now()

    def is_time_series(self, get_group):
        # check if the report support time series
        if self.is_valid():
            check = self.cleaned_data['time_series_pattern']
            if check == '': return False
            scope = self.cleaned_data['time_series_scope']
            if scope == 'both':
                return True
            elif scope == 'group' and get_group:
                return True
            elif scope == 'details' and not get_group:
                return True

        return False

    def get_time_series(self):
        _values = []
        if self.is_valid():
            series = self.cleaned_data['time_series_pattern']
            if series:
                if series == 'daily':
                    time_delta = datetime.timedelta(days=1)
                elif series == 'weekly':
                    time_delta = relativedelta(weeks=1)
                elif series == 'semimonthly':
                    time_delta = relativedelta(weeks=2)
                elif series == 'monthly':
                    time_delta = relativedelta(months=1)
                elif series == 'quarterly':
                    time_delta = relativedelta(months=3)
                elif series == 'semiannually':
                    time_delta = relativedelta(months=6)
                elif series == 'annually':
                    time_delta = relativedelta(year=1)
                else:
                    raise NotImplementedError()

                milli_time_detla = relativedelta(microseconds=5)

                done = False
                start_date = self.get_from_doc_date()  # - time_delta

                while not done:
                    dt = start_date + time_delta
                    start_date = dt
                    _values.append(dt - milli_time_detla)
                    if dt > self.get_to_doc_date():
                        done = True
        return _values

    def get_group_by_display(self):
        _values = []
        group_by = self.get_group_by_filters()
        if self.cleaned_data.get('add_details_control', False):
            _values.append('_control_')
        if group_by != 'doc_type':
            # _values.append(group_by + '_id')
            _values.append('id')
            ordered_cols = apply_order_to_list(self.cleaned_data['group_columns'],
                                               self.cleaned_data['group_col_order'].split(','))
            for item in ordered_cols:
                # if item == 'slug' and group_by:
                #     _values.append(group_by + '__slug')
                # elif item == 'title' and group_by:
                #     _values.append(group_by + '__title')
                # else:
                _values.append(item)
        else:
            # allowed_document_magic_fields = self.allowed_document_magic_fields
            selected_fields = self.cleaned_data['group_columns']
            if group_by == 'doc_date':
                _values.append('doc_date')
            elif group_by == 'slug':
                _values.append('slug')
                _values.append('doc_date')
            elif group_by == 'doc_type':
                _values.append('__doc_typeid__')
                _values.append('doc_type')
                allowed_document_magic_fields = self.magic_fields
                if 'slug' in selected_fields:
                    selected_fields.remove(u'slug')

            allowed_magic = [e for allowed in allowed_document_magic_fields for e in selected_fields if e in allowed]
            if allowed_magic:
                _values += allowed_magic
        return _values

    def clean(self):
        """
        Logical clean & validation of the reporting form
        @return:
        """
        cleaned_data = super(BaseReportForm, self).clean()
        msg = None
        group_by = cleaned_data.get('group_by', '')
        aggregate_on = cleaned_data.get('aggregate_on', '')

        time_series_scope = cleaned_data.get('time_series_scope', '')
        if group_by in ['slug', 'doc_date'] and cleaned_data['time_series_pattern']:
            msg = "Can't do time series on a group of slugs"
        elif cleaned_data.get('aggregate_on', '') == 'doc_date' and cleaned_data['time_series_scope'] != 'group':
            msg = "Can't do time series on a aggregate of doc_date"

        elif time_series_scope in ['details', 'both'] and aggregate_on == '':
            msg = 'Cant do time series on documents'

        if msg:
            raise forms.ValidationError(msg)

        return cleaned_data

    def is_matrix_support(self, get_group):
        if self.is_valid():
            check = self.cleaned_data['matrix']
            return check

        return False

    def get_matrix_fields(self):
        report_columns = self.cleaned_data['matrix_columns']
        series = self.get_matrix_ids()
        if self.cleaned_data['matrix_show_other']:
            series.append('----')
        entity_name = self.cleaned_data['matrix']
        series = [entity_name + '-' + id for id in series if id != '']

        report_columns = [col[:-1] + 'MX' for col in report_columns]

        _values = []
        if series:
            _values = [col + dt for dt in series for col in report_columns]
        return _values

    def get_matrix_ids(self):
        return [str(x.pk) for x in self.cleaned_data['matrix_entities']]

    def get_filter_from_matrix_field(self, field):
        entity = field.split('_MX')[1]
        entity = entity.split('-')
        _id = entity[1]
        entity = entity[0] + '_id'
        if _id == '' or _id == u'':
            selected_entities = self.get_matrix_ids()
            # selected_entities = [e.encode('ascii', 'ignore') for e in selected_entities if e != '']
            entity += '__in'
            q = Q(**{entity: selected_entities})
            q = ~q
            return (q,)

        return {entity: _id}

    def get_form_doc_types(self):
        if self.is_valid():
            return self.cleaned_data.get('doc_types', [])
        return []

    def get_matrix_core_columns(self):
        series = self.get_matrix_ids()
        if self.cleaned_data['matrix_show_other'] is True and series:
            series.append('----')
        entity_name = self.cleaned_data['matrix']
        series = [entity_name + '-' + id for id in series if id != '']
        return series

    def get_time_series_columns(self, get_group=True, plain=False):
        """
        Return time series columns
        :param get_group: current scope
        :param plain: if True it returns '__total__' instead of '__total_TS011212'
        :return: List if columns
        """
        _values = []
        if self.is_time_series(get_group):
            if get_group:
                cols = self.cleaned_data['time_series_fields']
            else:
                cols = self.cleaned_data['time_series_display']
            if plain:
                # list(cols) because we want a copy and not a
                # direct reference to cleaned_data['group_time_series']
                return list(cols)

            series = self.get_time_series()
            _values = [col + 'TS' + dt.strftime('%Y%m%d') for dt in series
                       for col in list(cols)]
        return _values

    def get_matrix_columns(self):
        check = self.is_matrix_support(True)
        if not check:
            return []

        report_columns = self.cleaned_data['matrix_columns']

        return list(report_columns)


# def analyze_report_model(report_model, base_model, doc_types_filter_func, magic_fields_filer_func=None, **kwargs):
#     doc_types_filter_func = doc_types_filter_func or (lambda x: x)
#     magic_fields_filer_func = magic_fields_filer_func or (lambda x: x)
#
#     magic_fields = field_registry.get_all_report_fields_names()
#     magic_fields = magic_fields_filer_func(magic_fields)
#
#     fkeys_map = get_foreign_keys(report_model)
#
#     doc_types_raw = base_model.get_doc_types()
#     doc_types_magical_field = doc_types_filter_func(doc_types_raw)
#     magic_fields += doc_types_magical_field
#
#     _movmenet_fields = get_model_fields2(report_model, None, all_fields=True, no_recurse=False,
#                                          recurse_name_slug_only=True, exclude_movement=True)
#
#     return {
#         'fk_map': fkeys_map,
#         'fields': _movmenet_fields,
#         'doc_types_magical_fields': doc_types_magical_field,
#         'doc_types': doc_types_raw,
#     }
class EasyMultipleChoiceField(forms.MultipleChoiceField):
    def to_python(self, value):
        if not value:
            return []
        elif not isinstance(value, (list, tuple)):
            raise ValidationError(self.error_messages['invalid_list'], code='invalid_list')
        return [str(val) for val in value]

    def validate(self, value):
        """Validate that the input is a list or tuple."""
        if self.required and not value:
            raise ValidationError(self.error_messages['required'], code='required')
        # Validate that each value in the value list is in self.choices.
        for val in value:
            # This will be moved somewhere else
            if '__' in val: continue
            if not self.valid_value(val):
                raise ValidationError(
                    self.error_messages['invalid_choice'],
                    code='invalid_choice',
                    params={'value': val},
                )


def _default_foreign_key_widget(f_field):
    return {'form_class': forms.ModelMultipleChoiceField,
            'required': False,
            'widget': RaAutocompleteSelectMultiple(f_field.remote_field, ra_admin_site,
                                                   attrs={'class': 'select2bs4'})}


def report_form_factory(model, base_model=None,
                        admin=True, magic_fields_filer_func=None,
                        fkeys_filter_func=None, doc_types_filter_func=None, foreign_key_widget_func=None,
                        **kwargs):
    '''
    fkeys_filter_func： a functin to filter out foreign keys detected by function,
    it gets a dictionary with foreignkey field name as key and the value the ForeignKey istance
    foreign_key_widget_func: a function to
    '''

    fkeys_filter_func = fkeys_filter_func or (lambda x: x)
    magic_fields_filer_func = magic_fields_filer_func or (lambda x: x)
    doc_types_filter_func = doc_types_filter_func or (lambda x: x)
    foreign_key_widget_func = foreign_key_widget_func or _default_foreign_key_widget

    magic_fields = field_registry.get_all_report_fields_names()
    magic_fields = magic_fields_filer_func(magic_fields)

    fields = OrderedDict()
    base_model_list = []
    fkeys_list = []

    if base_model is not None:
        if type(base_model) is str:
            base_model_name = base_model
        else:
            base_model_name = base_model.__name__.lower()
        base_model_list.append(base_model_name)

    time_series_options = ['daily', 'weekly', 'semimonthly', 'monthly', 'quarterly', 'semiannually', 'annually']

    try:
        doc_types_raw = base_model.get_doc_types()
    except AttributeError:
        # The base model does not follow the assumption of get_doc_types
        doc_types_raw = []
        pass

    doc_types_raw = doc_types_filter_func(doc_types_raw)
    doc_types_magical_field = ['__doc_type_%s__' % doc for doc in list(doc_types_raw)]

    magic_fields += doc_types_magical_field

    fkeys_map = get_foreign_keys(model)
    fkeys_map = fkeys_filter_func(fkeys_map)

    _movmenet_fields = get_model_fields2(model, all_fields=True, no_recurse=False,
                                         recurse_name_slug_only=True, exclude_movement=True)  # get_id_and_slug=True
    magic_fields_ordered = apply_order_to_list(magic_fields,
                                               ['__fb__', '__debit__', '__credit__', '__total__', '__balance__',
                                                '__last_doc_date__', '__doc_count__', '__line_count__'])

    fk_choices = [(k.replace('_id', ''), v.verbose_name) for k, v in fkeys_map.items()]

    scopes = choices_from_list(['group', 'details', 'both'], False)
    if admin:

        fields['group_by'] = forms.ChoiceField(required=False, widget=forms.Select(),
                                               choices=fk_choices + [('doc_type', _('doc_type'))],
                                               label=_('group by'))
        _grp_display = ['slug', 'title'] + magic_fields

        default_for_group_display = []
        fields['group_columns'] = EasyMultipleChoiceField(required=False, widget=forms.SelectMultiple(),
                                                          choices=choices_from_list(_grp_display, False) +
                                                                  choices_from_list(_movmenet_fields, False,
                                                                                    extra_list=magic_fields_ordered),
                                                          initial=default_for_group_display,
                                                          label=ugettext_lazy('group_columns'))

        fields['aggregate_on'] = forms.ChoiceField(required=False, widget=forms.Select(),
                                                   choices=[('', '----'), ] + fk_choices,
                                                   label=ugettext_lazy('aggregate_on'))

        default_display = list(_movmenet_fields)
        try:
            default_display.remove('creation_date')
            default_display.remove('lastmod')
        except ValueError:
            pass

        default_display += ['__fb__', '__debit__', '__credit__', '__balance__']
        fields['details_columns'] = forms.MultipleChoiceField(required=False, widget=forms.SelectMultiple(),
                                                              choices=choices_from_list(_movmenet_fields, False,
                                                                                        extra_list=magic_fields_ordered),
                                                              initial=default_display, label=_('details_columns'))

        time_series_options = choices_from_list(time_series_options)
        default_for_time_series = ['__balance__']  # todo: fix Bug __last_doc_date__
        fields['time_series_pattern'] = forms.ChoiceField(choices=time_series_options,
                                                          widget=forms.Select(), required=False,
                                                          label=_('time series pattern'))

        fields['time_series_fields'] = forms.MultipleChoiceField(required=False, widget=forms.SelectMultiple(),
                                                                 choices=choices_from_list(magic_fields, False),
                                                                 label=_('time series fields'),
                                                                 initial=default_for_time_series)

        fields['time_series_display'] = forms.MultipleChoiceField(required=False, widget=forms.SelectMultiple(),
                                                                  choices=choices_from_list(magic_fields, False),
                                                                  label=_('details time series display'),
                                                                  initial=default_for_time_series)

        fields['time_series_scope'] = forms.ChoiceField(required=False, widget=forms.Select,
                                                        choices=scopes, label=_('time series scope'), initial='group')

        movement_or_balance_choices = choices_from_list(['balance', 'movement'], False)
        fields['movement_or_balance'] = forms.ChoiceField(required=False, widget=forms.Select,
                                                          label=_('computation type'),
                                                          choices=movement_or_balance_choices, initial='movement')

        fields['doc_types'] = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple(),
                                                        choices=choices_from_list(doc_types_raw,
                                                                                  append_none=False),
                                                        initial=doc_types_raw,
                                                        label=_('doc types'))

        fields['group_col_order'] = forms.CharField(max_length=255, required=False, widget=forms.HiddenInput)
        fields['details_col_order'] = forms.CharField(max_length=255, required=False, widget=forms.HiddenInput)
        fields['print_group_title'] = forms.CharField(max_length=50, required=False, label=_('print group title'))
        fields['print_details_title'] = forms.CharField(max_length=50, required=False, label=_('print details title'))

        fields['custom_group_column_names'] = forms.CharField(max_length=10000, required=False,
                                                              label=_('Custom group column names'))
        fields['custom_details_column_names'] = forms.CharField(max_length=10000, required=False,
                                                                label=_('Custom details column names'))

    fields['from_doc_date'] = RaDateDateTimeField(required=False, label=capfirst(ugettext_lazy('from date')),
                                                  initial=app_settings.RA_DEFAULT_FROM_DATETIME,
                                                  widget=RaBootstrapDateTime(),
                                                  input_date_formats=['%Y-%m-%d', '%Y-%m-%d'],
                                                  input_time_formats=['%H:%M', '%H:%M:%S'])

    to_date_initial = datetime.datetime.combine(now().date() + datetime.timedelta(days=1), datetime.time.min)
    fields['to_doc_date'] = RaDateDateTimeField(required=False,
                                                initial=app_settings.RA_DEFAULT_TO_DATETIME,
                                                label=capfirst(ugettext_lazy('to date')), widget=RaBootstrapDateTime(),
                                                input_date_formats=['%Y-%m-%d', '%Y-%m-%d'],
                                                input_time_formats=['%H:%M', '%H:%M:%S'])

    fields['can_edit_primary_index'] = forms.BooleanField(required=False, initial=False,
                                                          label=_('can edit primary index'))
    fields['can_edit_secondary_index'] = forms.BooleanField(required=False, initial=False,
                                                            label=_('can edit secondary index'))
    fields['can_edit_time_series_pattern'] = forms.BooleanField(required=False, initial=False,
                                                                label=_('can edit timeseries pattern'))
    fields['can_edit_doc_types'] = forms.BooleanField(required=False, initial=False, label=_('can edit doc_types'))
    fields['can_edit_matrix_entities'] = forms.BooleanField(required=False, initial=True,
                                                            label=_('can edit matrix entities'))

    fields['matrix'] = forms.ChoiceField(choices=[('', '----'), ] + fk_choices, label=_('matrix support'),
                                         required=False,
                                         widget=forms.Select())
    fields['matrix_columns'] = forms.MultipleChoiceField(choices=choices_from_list(magic_fields_ordered, False),
                                                         label=_('matirx fields'),
                                                         widget=forms.SelectMultiple, required=False,
                                                         initial=['__balance__'])

    fields['matrix_show_other'] = forms.BooleanField(required=False, widget=forms.CheckboxInput(),
                                                     label=_('Show [The rest]'), initial=True)
    fields['matrix_entities'] = forms.CharField(required=False, label=_('matrix entities'))

    fields['matrix_scope'] = forms.ChoiceField(required=False, widget=forms.Select,
                                               choices=scopes, label=_('matrix scope'), initial='both')

    for name, f_field in fkeys_map.items():
        fkeys_list.append(name)

        fields[name] = f_field.formfield(
            **foreign_key_widget_func(f_field))

    fields['doc_date'] = forms.DateField(input_formats=["%Y-%m-%d"], required=False, label=ugettext_lazy('at date'))

    fields['add_details_control'] = forms.BooleanField(required=False, initial=False)

    # Get_initial_form_settings
    initial_settings = {}
    for field in fields.keys():
        initial_settings[field] = fields[field].initial

    new_form = type('ReportForm', (BaseReportForm, forms.BaseForm,),
                    {"base_fields": fields,
                     '_fkeys': fkeys_list,
                     'initial_settings': initial_settings,
                     'base_model': base_model,
                     'foreign_keys': fkeys_map,
                     'magic_fields': magic_fields,
                     'document_report_fields': ['slug', 'doc_date', 'doc_type']
                     })

    return new_form

from __future__ import unicode_literals

import datetime
import logging
from inspect import isclass

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ImproperlyConfigured, FieldDoesNotExist
from django.db.models import F, Q
from django.utils.timezone import now

from django.utils.translation import ugettext_lazy

from ra.base.app_settings import RA_DEFAULT_FROM_DATETIME, RA_DEFAULT_TO_DATETIME
from ra.base.cache import get_cached_name, get_cached_slug
from ra.reporting.helpers import DECIMAL_FIELDS, DATE_FIELDS, apply_order_to_list, get_field_from_query_text
from ra.utils.views import get_decorated_slug, get_linkable_slug_title, re_time_series, make_linkable_field
from .registry import field_registry

logger = logging.getLogger(__name__)


class ReportGenerator(object):
    field_registry_class = field_registry
    """
    Class to generate a Json Object containing report data based on
    report form , main_queryset and teh report model
    """
    date_field = None
    print_flag = None
    list_display_links = []

    # V2
    group_by = None
    columns = None

    time_series_pattern = ''
    time_series_columns = None
    show_empty_records = None
    report_model = None
    crosstab_model = None
    crosstab_columns = None

    def __init__(self, report_model=None, start_date=None, end_date=None, date_field=None,
                 q_filters=None, kwargs_filters=None,
                 group_by=None, columns=None, time_series_pattern=None, time_series_columns=None,
                 crosstab_model=None, crosstab_columns=None, crosstab_ids=None, crosstab_compute_reminder=True,
                 swap_sign=False, show_empty_records=True,
                 main_queryset=None,
                 base_model=None, print_flag=False,
                 doc_type_plus_list=None, doc_type_minus_list=None, limit_records=False, ):

        super(ReportGenerator, self).__init__()

        self.report_model = self.report_model or report_model
        if not self.report_model:
            raise ImproperlyConfigured('report_model must be set on a class level or via init')

        self.start_date = start_date or datetime.datetime.combine(RA_DEFAULT_FROM_DATETIME.date(),
                                                                  RA_DEFAULT_FROM_DATETIME.time())

        self.end_date = end_date or datetime.datetime.combine(RA_DEFAULT_TO_DATETIME.date(),
                                                              RA_DEFAULT_TO_DATETIME.time())
        self.date_field = self.date_field or date_field
        if not self.date_field:
            raise ImproperlyConfigured('date_field must be set on a class level or via init')

        self.q_filters = q_filters or []
        self.kwargs_filters = kwargs_filters or {}

        self.crosstab_model = crosstab_model or self.crosstab_model
        self.crosstab_columns = crosstab_columns or self.crosstab_columns
        self.crosstab_ids = crosstab_ids or []
        self.crosstab_compute_reminder = crosstab_compute_reminder

        main_queryset = main_queryset or self.report_model.objects

        self.base_model = base_model

        self.columns = self.columns or columns
        # import pdb ; pdb.set_trace()
        self.group_by = self.group_by or group_by

        self.time_series_pattern = time_series_pattern
        self.time_series_columns = time_series_columns

        self._prepared_results = {}
        self.report_fields_classes = {}

        self._report_fields_dependencies = {'time_series': {}, 'crosstab': {}, 'normal': {}}
        self.existing_dependencies = {'series': [], 'matrix': [], 'normal': []}

        self.print_flag = print_flag or self.print_flag
        #

        if self.group_by:
            try:
                self.group_by_field = [x for x in self.report_model._meta.fields if x.name == self.group_by][0]
            except IndexError:
                raise ImproperlyConfigured(
                    f'Can not find group_by field:{self.group_by} in report_model {self.report_model} ')

            self.focus_field_as_key = self.group_by
            self.group_by_field_attname = self.group_by_field.attname
        else:
            self.focus_field_as_key = None
            self.group_by_field_attname = None

        # doc_types = form.get_doc_type_plus_minus_lists()
        doc_types = [], []
        self.doc_type_plus_list = list(doc_type_plus_list) if doc_type_plus_list else doc_types[0]
        self.doc_type_minus_list = list(doc_type_minus_list) if doc_type_minus_list else doc_types[1]

        self.swap_sign = swap_sign
        self.limit_records = limit_records

        # passed to the report fields
        # self.date_field = date_field or self.date_field

        # in case of a group by, do we show a grouped by model data regardless of their appearance in the results
        # a client who didnt make a transaction during the date period.
        self.show_empty_records = self.show_empty_records or show_empty_records

        self.time_series_columns = time_series_columns or []
        self.time_series_pattern = time_series_pattern

        # Preparing actions
        self._parse()
        if self.group_by:
            if self.show_empty_records:
                self.main_queryset = self.group_by_field.related_model.objects.values()
            else:
                self.main_queryset = self.apply_queryset_options(main_queryset)
                ids = main_queryset.values_list(self.group_by_field.attname)
                self.main_queryset = self.group_by_field.related_model.objects.filter(pk__in=ids).values()
        else:
            self.main_queryset = self.apply_queryset_options(main_queryset, self.get_database_columns())

        self._prepare_report_dependencies()
        # self.prepare_calculation()

    def apply_queryset_options(self, query, fields=None):
        """
        Apply the filters to the main queryset which will computed results be mapped to
        :param query:
        :param fields:
        :return:
        """

        f = self.get_queryset_filters(w_date=True)
        if f:
            query = query.filter(**f)
        # import pdb; pdb.set_trace()
        if fields:
            return query.values(*fields)
        return query.values()

    def get_queryset_filters(self, w_date=True):
        """
        A hook between the view and the form
        :param w_date:
        :param w_doc_types:
        :return:
        """
        if w_date:
            date_filters = {
                f'{self.date_field}__gt': self.start_date,
                f'{self.date_field}__lte': self.end_date,
            }
            date_filters.update(self.kwargs_filters)
            return date_filters
        return self.kwargs_filters

    def _crypt_key(self, col, _time):
        """
        generate key from a series column
        :param col: 
        :param _time: 
        :return:
        """
        col_key = col.split('__')[1]
        col_key = '__' + col_key + '__TS' + _time.strftime('%Y%m%d')
        return col_key

    def construct_crosstab_filter(self, col_data):
        # import pdb; pdb.set_trace()
        if col_data['is_reminder']:
            filter = [~Q(**{f"{col_data['model']}_id__in": self.crosstab_ids})]
        else:
            filter = [Q(**{f"{col_data['model']}_id": col_data['id']})]
        return filter

    def get_field_computation_class(self, field_name):
        return self.report_fields_classes[field_name]

    def _prepare_report_dependencies(self):
        from .fields import BaseReportField
        all_columns = (
            ('normal', self._parsed_columns),
            ('time_series', self._time_series_parsed_columns),
            ('crosstab', self._crosstab_parsed_columns),
        )
        for window, window_cols in all_columns:
            for col_data in window_cols:
                klass = col_data['ref']
                dependencies_names = []
                # try:

                if isclass(klass) and issubclass(klass, BaseReportField):
                    dependencies_names = klass.get_full_dependency_list()

                    # check if any of this dependencies is on the report
                    fields_on_report = [x for x in window_cols if x['ref'] in dependencies_names]
                    for field in fields_on_report:
                        self._report_fields_dependencies[window][field['name']] = col_data['name']
            # import pdb; pdb.set_trace()
            for col_data in window_cols:
                klass = col_data['ref']
                # if getattr(klass, 'name', '') not in klasses_names:
                #     continue
                name = col_data['name']

                # if column has a dependency then skip it
                if not (isclass(klass) and issubclass(klass, BaseReportField)):
                    continue
                if self._report_fields_dependencies[window].get(name, False):
                    continue

                report_class = klass(self.doc_type_plus_list, self.doc_type_minus_list,
                                     self.report_model, date_field=self.date_field)
                # import pdb; pdb.set_trace()

                q_filters = None
                date_filter = {
                    f'{self.date_field}__gt': col_data.get('start_date', self.start_date),
                    f'{self.date_field}__lte': col_data.get('end_date', self.end_date),
                }
                date_filter.update(self.kwargs_filters)
                if window == 'crosstab':
                    q_filters = self.construct_crosstab_filter(col_data)

                # print(f'preparing {report_class} for {window}')
                report_class.prepare(self.focus_field_as_key, date_filter, q_filters)
                self.report_fields_classes[name] = report_class

    def get_record_data(self, obj, columns):
        """
        the function is run for every obj in the main_queryset
        :param obj: current row
        :param: columns： The columns we iterate on
        :return: a dict object containing all needed data
        """

        # todo , if columns are empty for whatever reason this will throw an error
        display_link = self.list_display_links or columns[0]
        data = {}
        group_by_val = None
        if self.group_by:
            column_data = obj.get(self.group_by_field_attname, obj.get('id'))
            group_by_val = str(column_data)

        # for i, col_data in enumerate(columns):
        for window, window_cols in columns:
            for col_data in window_cols:

                name = col_data['name']

                if name.startswith('__') and self.group_by:
                    source = self._report_fields_dependencies[window].get(name, False)
                    if source:
                        computation_class = self.get_field_computation_class(source)
                        value = computation_class.get_dependency_value(self.focus_field_as_key, group_by_val,
                                                                       col_data['ref'].name)
                    else:
                        try:
                            computation_class = self.get_field_computation_class(name)
                        except KeyError:
                            continue
                        # dep_results = self.get_dependencies_results(name, extra_key, dep_key)
                        # print(name, group_by_val, computation_class)
                        # import pdb; pdb.set_trace()
                        value = computation_class.resolve(self.focus_field_as_key, group_by_val)
                    if self.swap_sign: value = -value
                    data[name] = value

                else:
                    data[name] = obj.get(name, '')
                if self.group_by and name in display_link:
                    data[name] = make_linkable_field(self.group_by_field.related_model, group_by_val, data[name])

        return data

    def get_report_data(self):
        main_queryset = self.main_queryset
        if self.limit_records:
            main_queryset = main_queryset[:self.limit_records]

        all_columns = (
            ('normal', self._parsed_columns),
            ('time_series', self._time_series_parsed_columns),
            ('crosstab', self._crosstab_parsed_columns),
        )

        get_record_data = self.get_record_data
        data = [get_record_data(obj, all_columns) for obj in main_queryset]
        data = [x for x in data if x]

        return data

    def _parse(self):
        from .registry import field_registry

        if self.group_by:
            self.group_by_field = [x for x in self.report_model._meta.fields if x.name == self.group_by][0]
            self.group_by_model = self.group_by_field.related_model

        self.parsed_columns = []
        for col in self.columns:
            # import pdb; pdb.set_trace()
            attr = getattr(self, col, None)
            if attr:
                col_data = {'name': col,
                            'verbose_name': getattr(attr, 'verbose_name', col),
                            # 'type': 'method',
                            'ref': attr,
                            'type': 'text'
                            }
            elif col.startswith('__'):
                # a magic field
                if col in ['__time_series__', '__crosstab__']:
                    #     These are placeholder not real computation field
                    continue

                magic_field_class = field_registry.get_field_by_name(col)
                col_data = {'name': col,
                            'verbose_name': magic_field_class.verbose_name,
                            'source': 'magic_field',
                            'ref': magic_field_class,
                            'type': magic_field_class.type}
            else:
                # A database field
                model_to_use = self.group_by_model if self.group_by else self.report_model
                try:
                    if '__' in col:
                        # A traversing link order__client__email
                        field = get_field_from_query_text(col, model_to_use)
                    else:
                        field = model_to_use._meta.get_field(col)
                except FieldDoesNotExist:
                    raise FieldDoesNotExist(
                        f'Field {col} not found as an attribute to the generator class, nor as computation field, nor as a database column for the model {model_to_use._meta.model_name}')

                col_data = {'name': col,
                            'verbose_name': field.verbose_name,
                            'source': 'database',
                            'ref': field,
                            'type': field.get_internal_type()
                            }
            self.parsed_columns.append(col_data)

            self._parsed_columns = list(self.parsed_columns)
            self._time_series_parsed_columns = self.get_time_series_parsed_columns()
            self._crosstab_parsed_columns = self.get_crosstab_parsed_columns()

    def get_database_columns(self):
        return [col['name'] for col in self.parsed_columns if col['source'] == 'database']

    def get_method_columns(self):
        return [col['name'] for col in self.parsed_columns if col['type'] == 'method']

    def get_list_display_columns(self):
        columns = self.parsed_columns
        if self.time_series_pattern:
            time_series_columns = self.get_time_series_parsed_columns()
            try:
                index = self.columns.index('__time_series__')
                columns[index] = time_series_columns
            except ValueError:
                columns += time_series_columns

        if self.crosstab_model:
            crosstab_columns = self.get_crosstab_parsed_columns()

            try:
                index = self.columns.index('__crosstab__')
                columns[index] = crosstab_columns
            except ValueError:
                columns += crosstab_columns

        return columns

    def get_time_series_parsed_columns(self):
        """
        Return time series columns
        :param plain: if True it returns '__total__' instead of '__total_TS011212'
        :return: List if columns
        """
        _values = []

        cols = self.time_series_columns or []
        series = self._get_time_series_dates()

        for dt in series:
            for col in cols:
                try:
                    magic_field_class = field_registry.get_field_by_name(col)
                except:
                    magic_field_class = None

                _values.append({
                    'name': col + 'TS' + dt[1].strftime('%Y%m%d'),
                    'verbose_name': self.get_time_series_field_verbose_name(col, dt),
                    'ref': magic_field_class,
                    'start_date': dt[0],
                    'end_date': dt[1],
                })
        return _values

    def get_time_series_field_verbose_name(self, column_name, date_period):
        return column_name + date_period[1].strftime('%Y%m%d')

    def get_custom_time_series_dates(self):
        """
        Hook to get custom , maybe separated date periods
        :return: [ (date1,date2) , (date3,date4), .... ]
        """
        return []

    def _get_time_series_dates(self):
        _values = []
        series = self.time_series_pattern
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
            elif series == 'custom':
                return self.get_custom_time_series_dates()
            else:
                raise NotImplementedError()

            done = False
            start_date = self.start_date

            # import pdb; pdb.set_trace()
            while not done:
                to_date = start_date + time_delta
                _values.append((start_date, to_date))
                start_date = to_date
                if to_date > self.end_date:
                    done = True
        return _values

    def get_crosstab_parsed_columns(self):
        """
        Return a list of the columns analyzed , with reference to computation field and everything
        :return:
        """
        report_columns = self.crosstab_columns or []
        ids = list(self.crosstab_ids)
        if self.crosstab_compute_reminder:
            ids.append('----')
        output_cols = []
        ids_length = len(ids) - 1
        for counter, id in enumerate(ids):
            for col in report_columns:
                # try:
                magic_field_class = field_registry.get_field_by_name(col)
                # except:
                #     magic_field_class = None

                output_cols.append({
                    'name': f'{col}CT{id}',
                    'verbose_name': self.get_crosstab_field_verbose_name(col, id),
                    'ref': magic_field_class,
                    'id': id,
                    'model': self.crosstab_model,
                    'is_reminder': counter == ids_length
                })

        return output_cols

        # entity_name = self.crosstab_model
        # ids = [entity_name + '-' + id for id in ids if id != '']
        #
        # report_columns = [col + 'MX' for col in report_columns]
        #
        # _values = []
        # if ids:
        #     _values = [col + dt for dt in ids for col in report_columns]
        # return _values

    def get_crosstab_field_verbose_name(self, col, id):
        return f'{col}CT{id}'

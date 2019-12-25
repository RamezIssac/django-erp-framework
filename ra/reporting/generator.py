from __future__ import unicode_literals
import logging
from django.core.exceptions import ImproperlyConfigured
from django.db.models import F


from django.utils.translation import ugettext_lazy

from ra.base.cache import get_cached_name, get_cached_slug
from ra.reporting.helpers import DECIMAL_FIELDS, DATE_FIELDS, apply_order_to_list
from ra.utils.views import get_decorated_slug, get_linkable_slug_title, re_time_series
from .registry import field_registry

logger = logging.getLogger(__name__)


class ReportGenerator(object):
    field_registry_class = field_registry
    """
    Class to generate a Json Object containing report data based on
    report form , main_queryset and teh report model
    """

    def __init__(self, report_model, form, main_queryset, no_distinct=False, base_model=None, print_flag=False,
                 doc_type_plus_list=None, doc_type_minus_list=None, limit_records=False, swap_sign=False):
        super(ReportGenerator, self).__init__()
        if no_distinct and not base_model:
            raise ImproperlyConfigured('If no_distinct is True then have to supply as base_model ')

        self.report_model = report_model
        self.form = form
        self.base_model = base_model
        self.fk_filters = form.get_fk_filters()
        self.date_filters = form.get_date_filters()
        self.doc_type_filters = form.get_doc_types_filters()
        self.columns = []
        self.time_series_columns = []
        self.matrix_columns = []

        self._prepared_results = {}
        self.report_fields_classes = {}
        self.report_fields_dependencies = {'series': {}, 'matrix': {}, 'normal': {}}
        self.existing_dependencies = {'series': [], 'matrix': [], 'normal': []}
        self._imposed_start_date = False

        self.print_flag = print_flag
        #
        self.group_by = form.get_group_by_filters()

        self.get_group = True  # bool(self.group_by)
        if self.group_by:
            self.focus_field_as_key = self.group_by
            self.focus_field_id = self.group_by + '_id' if self.group_by not in ['doc_type', 'doc_date',
                                                                                 'slug'] else self.group_by
        else:
            self.focus_field_as_key = None
            self.focus_field_id = None

        self._fk2_field = self.focus_field_id

        doc_types = form.get_doc_type_plus_minus_lists()
        self.doc_type_plus_list = list(doc_type_plus_list) if doc_type_plus_list else doc_types[0]
        self.doc_type_minus_list = list(doc_type_minus_list) if doc_type_minus_list else doc_types[1]

        self.need_running_total = False
        self.swap_sign = swap_sign
        self.limit_records = limit_records
        #
        self.main_queryset = self.apply_queryset_options(main_queryset, no_distinct)
        self._prepare_decimal_fields()
        self._prepare_report_fields()
        self.prepare_calculation()

    def apply_queryset_options(self, query, no_distinct):
        """
        Apply the filters to the main queryset which will computed results be mapped to
        :param query: 
        :return:
        """
        if no_distinct:
            return self._get_no_distinct_queryset()
        distinct_filter = self.form.get_group_by_filters()
        self.group_by = distinct_filter
        if self.get_group and distinct_filter:
            query = query.distinct(distinct_filter)
            f = self.form_get_queryset_filters(w_doc_types=False, w_date=False)
        else:
            f = self.form_get_queryset_filters(w_date=True)
            if self._imposed_start_date:
                user_date = f['doc_date__gt']
                if user_date < self._imposed_start_date:
                    f['doc_date__gt'] = self._imposed_start_date
        if f:
            query = query.filter(**f)
        return query.values()

    def form_get_queryset_filters(self, w_date=True, w_doc_types=True):
        """
        A hook between the view and the form
        :param w_date:
        :param w_doc_types:
        :return:
        """
        return self.form.get_queryset_filters(w_date, w_doc_types)

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

    def _decrypt_matrix_col(self, col, w_check=False):

        col_key = col.split('_MX')
        if len(col_key) == 1:
            return False, None, None

        filter = self.form.get_filter_from_matrix_field(col)  # {field[0] + '_id': field[1]}
        col = col_key[0] + '__'
        field = col_key[1].split('-')

        if w_check:
            return True, col, field
        return col, field, filter

    def extract_time_series(self, name):
        is_time_field = re_time_series.findall(name)
        return is_time_field or False

    def _prepare_decimal_fields(self):
        """
        Create a set of decimal fields names for faster search instead of
        normal unordered list
        :return: set {}
        """
        append = {'value', 'price', 'quantity', 'discount'}
        decimal_fields = list(DECIMAL_FIELDS) + self.form.get_form_doc_types()
        self._decimal_fields = set([d[:-1] for d in decimal_fields]) | append

    def get_field_computation_class(self, field_name):
        return self.report_fields_classes[field_name]

        # from .fields import BaseReportField
        # return BaseReportField(self.doc_type_plus_list, self.doc_type_minus_list, self.report_model)

    def _prepare_report_fields(self):
        """
        loops over the computation fields in the report, load and instantiate them
        and store them in class variable , prepare fields dependency
        Case: __credit__ field require __total__ , so does __debit__
        we need to make sure that __debit__ does not recompute total and use the prepared value in credit
        """
        registry = self.field_registry_class

        series_fields = self.form.get_time_series_columns(self.get_group, True)
        series_fields = [x for x in series_fields if x.startswith('__')]
        series_fields_number = (0, len(series_fields))
        matrix_fields = self.form.get_matrix_columns(self.get_group, True)
        matrix_fields = [x for x in matrix_fields if x.startswith('__')]
        matrix_fields_number = (len(series_fields), len(matrix_fields))
        normal_fields = self.form.get_datatable_columns(self.get_group, False, False, False)
        normal_fields = [x for x in normal_fields if x.startswith('__')]
        normal_fields_number = (
            len(series_fields) + len(matrix_fields), len(series_fields) + len(matrix_fields) + len(normal_fields))
        all_fields = series_fields + matrix_fields + normal_fields
        for i, col in enumerate(all_fields):
            # todo: enhance the check, feels very weak
            if col == '__doc_typeid__': continue
            # store dependency map in the appropriate key
            if i >= series_fields_number[0] and i < series_fields_number[1]:
                key = 'series'
                fields_on_report = series_fields
            elif i >= matrix_fields_number[0] and i < matrix_fields_number[1]:
                key = 'matrix'
                fields_on_report = matrix_fields
            elif i >= normal_fields_number[0] and i < normal_fields_number[1]:
                key = 'normal'
                fields_on_report = normal_fields
            else:
                assert False

            klass = registry.get_field_by_name(col)
            dependencies = klass.get_full_dependency_list()

            self.existing_dependencies[key] += list(dependencies)

            # FieldReport can call calculation for its dependencies
            # However, as some dependencies are already on the report and gonna be computed anyway
            # so we look for only those not on the report, store them and make FieldReport compute only those.

            compute_dependency = []
            existing_dependency = []
            for d in dependencies:
                if d.name not in fields_on_report:
                    compute_dependency.append(d.name)
                else:
                    existing_dependency.append(d.name)

            self.report_fields_dependencies[key][col] = {
                'computed_by_field': compute_dependency,
                'existing_on_report': existing_dependency
            }
            self.report_fields_classes[col] = klass(self.doc_type_plus_list, self.doc_type_minus_list,
                                                    self.report_model)

    def prepare_calculation(self):
        group_by_field = self.focus_field_as_key
        # time_series = [('startof_year', 'now')]
        # for period in time_series:
        #     pass

        crypt_key = False
        matrix_index = None
        timeseries_index = None
        column_container = []  # holds two lists , time series fields if any & "normal" fields
        matrix_cols = []
        if self.form.is_time_series(self.get_group):
            times = self.form.get_time_series()
            repeat_columns = self.form.get_time_series_columns(self.get_group, plain=True)
            timeseries_index = len(column_container)
            column_container.append(repeat_columns)

        else:
            times = [self.form.get_to_doc_date()]

        if self.form.is_matrix_support(self.get_group):
            matrix_cols = self.form.get_matrix_fields()
            matrix_index = len(column_container)
            # matrix_entity = self.form.get_matrix_entity()
            column_container.append(matrix_cols)

        #
        # Appened other fields that are not part of the series
        # in order to get prepared too
        if self.get_group:
            column_container.append(self.form.get_group_by_display())
        else:
            column_container.append(self.form.get_datatable_columns(self.get_group, False, False, False))

        movement_total = 'movement'  # self.form.get_movement_or_balance()
        self.movement_computation = True

        i = 0
        matrix_fields = False
        for container in column_container:
            if i == timeseries_index:
                crypt_key = True
                current_iteration = 'series'
            elif i == matrix_index:
                crypt_key = False
                matrix_fields = True
                current_iteration = 'matrix'
            else:
                current_iteration = 'normal'
                matrix_fields = False
                crypt_key = False
                times = [self.form.get_to_doc_date()]  # added to prevent un-needed time iteration

            i += 1
            processed_col = []
            for col in container:
                previous_date = self.form.get_from_doc_date()

                # prevent duplication of matrix fiuelds computation which would lead to errors if happened
                if not matrix_fields and col in matrix_cols:
                    processed_col.append(col)

                if col.startswith('__') and col not in processed_col and col != '__doc_typeid__':
                    for _time in times:

                        cache_list = None
                        q_filters = None
                        doc_date_filter = {}
                        if crypt_key:
                            col_key = self._crypt_key(col, _time)  # f.extract_time_series(col):

                        elif matrix_fields:
                            col_key = col
                            col, entity, matrix_filter = self._decrypt_matrix_col(col)
                            if '----' in col_key:
                                q_filters = matrix_filter
                                matrix_filter = {}
                            else:
                                doc_date_filter.update(matrix_filter)
                        else:
                            doc_date_filter = {}
                            col_key = col

                        doc_date_filter['doc_date__gt'] = previous_date
                        doc_date_filter['doc_date__lte'] = _time

                        if self._imposed_start_date:
                            user_date = doc_date_filter['doc_date__gt']
                            if user_date < self._imposed_start_date:
                                doc_date_filter['doc_date__gt'] = self._imposed_start_date

                        if col.startswith('__doc_type_'):
                            quan_flag = False
                            x = col.split('__doc_type_')[1]
                            if 'quan' in x:
                                quan_flag = True
                                x = x.split('quan_')[1]
                            doc_type = x.split('__')[0]
                            cache_list = self._prepare_doc_types(doc_type, extra_filters=doc_date_filter,
                                                                 quan=quan_flag, q_filter=q_filters)
                        elif True:

                            filters = doc_date_filter.copy()
                            filters.update(self.fk_filters)
                            computation_class = self.get_field_computation_class(col)
                            # if i == timeseries_index:
                            dep_fields = self.report_fields_dependencies[current_iteration][col].get(
                                'computed_by_field', False)
                            cache_list = computation_class.prepare(group_by_field, filters, q_filters,
                                                                   bool(dep_fields), dep_fields)
                            if crypt_key:
                                col_key = self._crypt_key(col, _time)
                            elif not matrix_fields:
                                col_key = col

                        if movement_total == 'movement' and crypt_key:
                            previous_date = _time
                        self._prepared_results[col_key] = cache_list

    def get_dependencies_results(self, field, extra_key=None, dep_key=None):
        dep_results = {}
        dependencies = self.report_fields_dependencies[dep_key].get(field, {}).get('existing_on_report', [])

        for i in dependencies:
            dep_results[i + extra_key] = {
                'results': self._prepared_results[i + extra_key],
                'instance': self.get_field_computation_class(i)
            }
        return dep_results

    def get_datatable_options(self):
        # todo Revise and maybe delete

        is_group = self.get_group
        appened_fkeys = True

        if self.form.is_time_series(is_group):
            original_columns = self.form.get_datatable_columns(is_group, appened_fkeys, wTimeSeries=False)
            time_series_colums = self.form.get_time_series_columns(is_group)
            options = original_columns + time_series_colums

        elif self.form.is_matrix_support(is_group):
            original_columns = self.form.get_datatable_columns(is_group, appened_fkeys, wMatrix=False)
            time_series_colums = self.form.get_matrix_fields()
            options = original_columns + time_series_colums

        else:
            options = self.form.get_datatable_columns(is_group, appened_fkeys)

        self.datatable_structure = options
        options = {'columns': options}

        return options

    def get_record_data(self, obj):
        """
        the function is run for every obj in the main_queryset
        :param obj:
        :return:
        """

        options = self.get_datatable_options()
        columns = options['columns']

        data = {}
        extract_time_series = self.extract_time_series
        _decrypt_matrix_col = self._decrypt_matrix_col
        has_attr_fk2_field = hasattr(self, '_fk2_field')

        print_flag = self.print_flag
        fk2_field = None
        column_data = u''
        if has_attr_fk2_field and self._fk2_field:
            column_data = obj[self._fk2_field]
            # if six.PY2 and isinstance(column_data, str):  # not unicode
            #     column_data = column_data.decode('utf-8')

            fk2_field = str(column_data)

        _decimal_fields = self._decimal_fields

        for i, name in enumerate(columns):

            if name.startswith('__') and has_attr_fk2_field:
                is_time_field = extract_time_series(name)
                extra_key = ''
                if is_time_field:
                    extra_key = is_time_field[0]
                    magic_field_name = name.replace(is_time_field[0], '')
                    # magic_field_name += '_'
                    dep_key = 'series'
                else:
                    magic_field_name = name
                    dep_key = 'normal'

                matrix_check, _magic_field_name, entity = _decrypt_matrix_col(name, w_check=True)
                if matrix_check:
                    magic_field_name = _magic_field_name
                    dep_key = 'matrix'

                if magic_field_name == '__doc_typeid__':
                    # column_data = self.get_column_data(i, 'doc_type', obj)[0]
                    # data[name] = six.text_type(column_data)
                    data[name] = obj['doc_type']
                    continue

                # if is_time_field:
                #         cache_key = main_key + is_time_field[0]
                #     elif matrix_check:
                #         cache_key = name
                #     else:
                #         cache_key = main_key + '_'
                computation_class = self.get_field_computation_class(magic_field_name)
                dep_results = self.get_dependencies_results(magic_field_name, extra_key, dep_key)
                value = computation_class.resolve(self._prepared_results[name],
                                                  self.focus_field_as_key, fk2_field, dep_results)
                if self.swap_sign: value = -value
                data[name] = value

            else:
                # ie: not a magic Field
                if '__slug' in name:
                    model_name = name.split('__slug')[0]
                    # model_pk = obj.__getattribute__(model_name + '_id')
                    model_pk = obj[model_name + '_id']
                    if model_pk:
                        data[name] = get_cached_slug(model_name, model_pk)
                        if not print_flag:
                            data[name] = get_linkable_slug_title(model_name, model_pk, data[name])
                    else:
                        data[name] = ''

                elif '__title' in name:
                    model_name = name.split('__title')[0]
                    # model_pk = obj.__getattribute__(model_name + '_id')
                    model_pk = obj[model_name + '_id']
                    if model_pk:
                        # slug = get_cached_slug(model_name, model_pk)
                        title = get_cached_name(model_name, model_pk)
                        if not print_flag:
                            data[name] = get_linkable_slug_title(model_name, model_pk, title)
                        else:
                            data[name] = title

                    else:
                        data[name] = ''

                else:
                    # self._cache = None
                    # column_data = self.get_column_data(i, name, obj)[0]
                    column_data = obj.get(name, '')

                    # if name in obj:
                    #     if obj[name]:
                    #         column_data = obj[name]

                    # if name in DATE_FIELDS:
                    #     if not self.group_by == 'doc_date' and self.get_group:
                    #         column_data = column_data.strftime('%Y/%m/%d %H:%M')
                    #     else:
                    #         column_data = column_data.strftime('%Y-%m-%d')
                    if name in DATE_FIELDS:
                        data[name] = column_data
                    else:
                        # if six.PY2 and isinstance(column_data, str):  # not unicode
                        #     column_data = column_data.decode('utf-8')

                        data[name] = str(column_data)

                '''Apply redirect link'''
                if (name == 'slug') and not print_flag:
                    data[name] = get_decorated_slug(name, data[name], obj, True)

        if self.need_running_total:
            self.apply_running_total(obj, data, columns)
        if 'doc_type' in data:
            data['doc_type_raw'] = data['doc_type']
            data['doc_type'] = ugettext_lazy(data['doc_type'])

        # data = self.manipulate_data_line(data, obj)

        if data and has_attr_fk2_field and self._fk2_field:

            if data[self._fk2_field] == '' or data[self._fk2_field] == 'None':
                # short Circuit when it's an empty record due to annotation (most propably)
                return None
        # data = self.pre_json_response(data, obj)
        return data

    def apply_running_total(self, obj, data, columns):
        PRINT_FLAG = False
        if self.DOCUMENT_FLAG:
            value = self._get_value_for_running_total(obj)
        else:
            value = obj['value']
        quan = 0
        if self.group_by in ['doc_type', 'doc_date', 'slug']:
            group_by = self.group_by
        else:
            group_by = self.group_by + '_id'

        doc_type = obj['doc_type']
        if doc_type in self.doc_type_plus_list:
            adj_value = value
            if self.support_quan and 'quantity' in obj: quan = obj['quantity']
        else:
            adj_value = -value
            if self.support_quan and 'quantity' in obj: quan = -obj['quantity']

        if '__fb__' in columns:
            if self._previous_balance is None and obj['doc_type'] != 'fb':
                self._previous_balance = self.get_fb({}, group_by)
            data['__fb__'] = self._previous_balance

        if '__debit__' in columns:
            if doc_type in self.doc_type_plus_list:
                data['__debit__'] = value
            else:
                data['__debit__'] = '-' if not PRINT_FLAG else 0

        if '__credit__' in columns:
            if doc_type in self.doc_type_minus_list:

                data['__credit__'] = value
            else:
                data['__credit__'] = '-' if not PRINT_FLAG else 0

        if '__balance__' in columns:
            if self._previous_balance is not None:
                new_balance = self._previous_balance + (adj_value or 0)
            else:
                new_balance = adj_value
            data['__balance__'] = new_balance
            self._previous_balance = new_balance

        if '__fb_quan__' in columns:
            if self._previous_quan is None:
                self._previous_quan = self.get_fb({}, self.group_by + '_id', quan=True)
            data['__fb_quan__'] = self._previous_quan

        if '__debit_quan__' in columns:
            if doc_type in self.doc_type_plus_list:
                data['__debit_quan__'] = quan
            else:
                data['__debit_quan__'] = '-' if not PRINT_FLAG else 0

        if '__credit_quan__' in columns:
            if doc_type in self.doc_type_minus_list:

                data['__credit_quan__'] = quan
            else:
                data['__credit_quan__'] = '-' if not PRINT_FLAG else 0

        if '__balance_quan__' in columns:
            if self._previous_quan is not None:
                new_balance = self._previous_quan + quan
            else:
                new_balance = quan
            data['__balance_quan__'] = new_balance
            self._previous_quan = new_balance

        return data

    def get_report_data(self):
        main_queryset = self.main_queryset
        if self.limit_records:
            main_queryset = main_queryset[:self.limit_records]
        get_record_data = self.get_record_data
        data = [get_record_data(obj) for obj in main_queryset]
        data = [x for x in data if x]

        return data

    def get_ordered_columns(self, columns, order_list=None, is_group=None, is_time_series=False,
                            time_series_columns=None, **kwargs):

        if not order_list:
            order_list = self.form_settings.get('group_column_order', []) if is_group else self.form_settings.get(
                'details_column_order', [])

            put_back_control = False
            if columns[0] == '_control_':
                columns = columns[1:]
                put_back_control = True

            if is_time_series:
                columns = self.apply_order_time_series(columns, time_series_columns, order_list)
            else:
                columns = apply_order_to_list(columns, order_list)

            if put_back_control:
                columns = ['_control_'] + columns

            return columns

        return apply_order_to_list(columns, order_list)

    def _get_no_distinct_queryset(self):
        pk_name = self.base_model().get_pk_name()
        return self.base_model.objects.annotate(**{pk_name: F('id')}).values(pk_name)

from ra.reporting.registry import register_report_view
from ra.reporting.views import ReportView

from django.utils.translation import ugettext_lazy as _

from .models import Expense, ExpenseTransaction


@register_report_view
class ExpenseTotalReport(ReportView):
    report_title = _('Expense Totals')

    # that's the report url endpoint
    # So this report ajax request will be sent reports/<namespace>/<report_slug>
    # this should be unique to the namespace
    report_slug = 'balances'

    # here we define basic information for the report
    base_model = Expense

    # Where is the data to compute
    report_model = ExpenseTransaction

    group_by = 'expense'
    columns = ['slug', 'title', '__total__']
    chart_settings = [

        {
            'type': 'bar',
            'data_source': ['__total__'],
            'title_source': ['title'],
        },
        {
            'type': 'pie',
            'data_source': ['__total__'],
            'title_source': ['title'],
        },
    ]


@register_report_view
class ExpenseDetailedStatement(ReportView):
    base_model = Expense
    report_model = ExpenseTransaction

    report_title = _('Expense detailed statement')
    columns = ['slug', 'doc_date', 'doc_type', 'treasury__title', 'expense__title', 'value']
    # if app_settings.RA_SUPPORT_LIABILITY:
    #     columns += ['liability__slug', 'liability__title']


@register_report_view
class ExpenseMovementTimeComparison(ReportView):
    report_title = _('Expenses Monthly Movements')
    base_model = Expense
    report_model = ExpenseTransaction
    group_by = 'expense'
    time_series_pattern = 'monthly'
    columns = ['slug', 'title']
    time_series_columns = ['__total__']

    form_settings = {
        'default': True,
        'group_by': 'treasury',
        'aggregate_on': 'expense',
        'group_page_title': _('Expenses Monthly Movement'),
        'details_page_title': _('Expense Monthly Movement'),

        'time_series_pattern': 'monthly',
        'time_series_scope': 'both',
        'group_time_series_display': ['__total__'],
        'time_series_display': ['__total__'],

        'details_columns': ['treasury__slug', 'treasury__title', '__total__'],
        'details_column_order': ['treasury__slug', 'treasury__title', '__time_series__', '__total__'],

        'group_columns': ['slug', 'title', '__total__'],
        'group_column_order': ['treasury__slug', 'treasury__title', '__time_series__', '__total__'],
        'group_column_names': {
            '__total__': _('total expense movement'),
        },

        'time_series_TS_name': _('in'),

        'group_time_series_column_names': {
            '__total__': _('movement'),
        },

    }
    chart_settings = [
        {
            'id': 'total_movement_bar',
            'type': 'column',
            'title_source': 'title',
            'data_source': ['__total__'],
            'series_names': [_('total movement')],
            'stacking': 'normal',

        },
        # {
        #     'id': 'total_pie',
        #     'title': _('pie - sum'),
        #     'settings': {
        #         'chart_type': 'pie',
        #         'title': _('total movement comparison by month {expense}'),
        #         'sub_title': '{time_series_pattern} {date_verbose}',
        #         'y_sources': ['__total__'],
        #         'series_names': [_('total movement')],
        #         'plot_total': True
        #     }
        # },
        # {
        #     'id': 'balance_bar',
        #     'title': _('bar - detailed'),
        #     'settings': {
        #         'title': _('treasury expense comparison by month {expense}'),
        #         'sub_title': '{time_series_pattern} {date_verbose}',
        #         'chart_type': 'column',
        #         'y_sources': ['__total__'],
        #         'series_names': ['balance']
        #     }
        # },
    ]


@register_report_view
class ExpenseMovementMatrixComparison(ReportView):
    report_title = _('Expenses Comparison')
    base_model = Expense
    report_model = ExpenseTransaction

    group_by = 'treasury'
    crosstab_model = 'expense'
    crosstab_columns = ['__total__']
    columns = ['title']

    chart_settings = [
        {
            'type': 'column',
            'data_source': ['__total__'],
            'plot_total': False,
            'title_source': 'title',
        },
        {
            'type': 'column',
            'data_source': ['__total__'],
            'plot_total': False,
            'title_source': 'title',
            'stacking':'normal'
        },

        {
            'type': 'pie',
            'data_source': ['__total__'],
            'plot_total': False,
            'title_source': 'title',
        }
    ]

    #     'group_page_title': _('Expenses Comparison'),
    #     'details_page_title': _('Expenses Comparison'),
    #
    #     # 'time_series_pattern': 'monthly',
    #     # 'time_series_scope': 'both',
    #     # 'group_time_series_display': ['__total__'],
    #     # 'time_series_display': ['__total__'],
    #     'matrix': 'expense',
    #     'matrix_columns': ['__total__'],
    #     'matrix_columns_names': {
    #         '__total__': _('movement')
    #     },
    #
    #     'details_columns': ['treasury__slug', 'treasury__title', '__total__'],
    #     'details_column_order': ['treasury__slug', 'treasury__title', '__time_series__', '__total__'],
    #
    #     'group_columns': ['slug', 'title', '__total__'],
    #     'group_column_order': ['treasury__slug', 'treasury__title', '__time_series__', '__total__'],
    #     'group_column_names': {
    #         '__total__': _('total expense movement'),
    #     },
    #
    #     'time_series_TS_name': _('in'),
    #
    #     'group_time_series_column_names': {
    #         '__total__': _('movement'),
    #     },
    #
    # }

from django.utils.translation import ugettext_lazy as _
from ra.reporting.decorators import register_report_view
from ra.reporting.form_factory import report_form_factory
from ra.reporting.views import ReportView
from .models import Client, SimpleSales, Product


@register_report_view
class ClientTotalBalance(ReportView):
    report_title = _('Clients Balances')

    # that's the report url endpoint
    # So this report ajax request will be sent reports/<namespace>/<report_slug>
    # this should be unique to the namespace
    report_slug = 'balances'

    # here we define basic information for the report
    base_model = Client

    # Where is the data to compute
    report_model = SimpleSales

    # here is the meat and potatos of the report,
    # we group the sales per client , we display columns slug and title (of the `base_model` defied above
    # and we add the magic field `__balance__` we compute the client balance.
    form_settings = {'group_by': 'client',
                     'group_columns': ['slug', 'title', '__balance__'],
                     }

    group_by = 'client'
    columns = ['slug', 'title', '__balance__']
    chart_settings = [
        {
            'id': 'pie',
            'title': _('pie'),
            'settings': {
                'chart_type': 'pie',
                'title': _('Clients Balance'),
                'y_sources': ['__balance__'],
                'series_names': [_('Clients Balance')],
            }
        },
    ]


@register_report_view
class ClientTotalBalancesOrdered(ClientTotalBalance):
    report_slug = None
    default_order_by = '__balance__'


@register_report_view
class ClientTotalBalancesOrderedDESC(ClientTotalBalance):
    report_slug = None
    default_order_by = '-__balance__'


@register_report_view
class ProductTotalSales(ReportView):
    report_title = _('Product Sales')

    # identifier of the report
    # This report ajax request will be sent reports/<namespace>/<report_slug>
    # `report_slug` should be unique to the namespace
    report_slug = 'total_sales'

    # here we define basic information for the report
    base_model = Product

    # Where is the data to compute
    report_model = SimpleSales

    # here is the meat and potato of the report,
    # we group the records in SimpleSales by Client ,
    # And we display columns slug and title (relative to the `base_model` defined above)
    # the magic field `__balance__` computes the balance (of the base model)
    form_settings = {'group_by': 'product',
                     'group_columns': ['slug', 'title', '__balance__', '__balance_quan__'],
                     }
    group_by = 'product'
    columns = ['slug', 'title', '__balance__', '__balance_quan__']


@register_report_view
class ClientList(ReportView):
    report_title = _('Our Clients')

    # report_slug = 'client_list'
    base_model = Client
    report_model = SimpleSales

    hidden = True

    form_settings = {
        'group_by': 'client',
        'group_columns': ['slug', 'title'],
        'add_details_control': True,
    }
    group_by = 'client'
    columns = ['slug', 'title']


@register_report_view
class ProductClientSales(ReportView):
    base_model = Client
    report_model = SimpleSales

    report_slug = 'client_sales_of_products'
    report_title = _('Client net sales for each product')
    must_exist_filter = 'client_id'
    header_report = ClientList
    form_class = report_form_factory(report_model, base_model)

    form_settings = {
        'group_by': 'product',
        'group_columns': ['slug', 'title', '__balance_quan__', '__balance__'],
    }
    group_by = 'product'
    columns = ['slug', 'title', '__balance_quan__', '__balance__']

    chart_settings = [
        {
            'id': 'total_pie',
            'title': _('sales by client'),
            'settings': {
                'chart_type': 'pie',
                'title': _('sales for {product}'),

                'sub_title': _('{date_verbose}'),
                'y_sources': ['__balance_quan__'],
                'series_names': [_('Sales Qty')],
            }
        },
        {
            'id': 'total_bar',
            'title': _('sales by client (Bar)'),
            'settings': {
                'chart_type': 'column',
                'y_sources': ['__balance_quan__'],

                'title': _('sales for {product}'),
                'sub_title': _('{date_verbose}'),
                'series_names': [_('sales Qty')],
            }
        },

    ]


@register_report_view
class ProductSalesMonthlySeries(ReportView):
    base_model = Product
    report_model = SimpleSales
    report_title = _('Product Sales Monthly')

    form_settings = {
        'group_by': 'product',
        'group_columns': ['slug', 'title'],

        'time_series_pattern': 'monthly',
        'time_series_columns': ['__balance_quan__', '__balance__'],
    }

    group_by = 'product'
    columns = ['slug', 'title']
    time_series_pattern = 'monthly',
    time_series_columns = ['__balance_quan__', '__balance__']

    chart_settings = [
        {
            'id': 'movement_column',
            'title': _('comparison - column'),
            'settings': {
                'chart_type': 'column',
                'title': _('{product} Avg. purchase price '),
                'sub_title': _('{date_verbose}'),
                'y_sources': ['__balance__'],
                'series_names': [_('Avg. purchase price')],
            }
        },
        {
            'id': 'movement_line',
            'title': _('comparison - line'),
            'settings': {
                'chart_type': 'line',
                'title': _('{product} Avg. purchase price '),
                'sub_title': _('{date_verbose}'),
                'y_sources': ['__balance__'],
                'series_names': [_('Avg. purchase price')],
            }
        },
    ]


class ClientReportMixin:
    base_model = Client
    report_model = SimpleSales


@register_report_view
class ClientSalesMonthlySeries(ClientReportMixin, ReportView):
    report_title = _('Client Sales Monthly')
    base_model = Client
    report_model = SimpleSales

    # header_report = ProductSalesMonthlySeries
    # must_exist_filter = 'product_id'

    form_settings = {
        'group_by': 'client',
        'group_columns': ['slug', 'title'],

        'time_series_pattern': 'monthly',
        'time_series_columns': ['__debit__', '__credit__', '__balance__', '__total__'],
    }

    group_by = 'client'
    columns = ['slug', 'title']
    time_series_pattern = 'monthly'
    # time_series_columns = ['__debit__']
    time_series_columns = ['__debit__', '__credit__', '__balance__', '__total__']

@register_report_view
class ClientDetailedStatement(ReportView):
    report_title = _('client statement')
    base_model = Client
    report_model = SimpleSales

    header_report = ClientList
    must_exist_filter = 'client_id'

    form_settings = {
        'group_by': '',
        'group_columns': ['slug', 'doc_date', 'doc_type', 'product__title', 'quantity', 'price', 'value'],
    }

    columns = ['slug', 'doc_date', 'doc_type', 'product__title', 'quantity', 'price', 'value']


@register_report_view
class ProductClientSalesMatrix(ReportView):
    base_model = Product
    report_model = SimpleSales
    report_title = _('Matrix')

    form_settings = {
        'group_by': 'client',
        'group_columns': ['slug', 'title'],
        'group_column_order': ['product__slug', 'product__title',
                               '__total__',
                               '__balance__'],
        'matrix': 'client',
        'matrix_columns': ['__total__'],
        'matrix_columns_names': {
            '__total__': _('movement')
        },
    }
    swap_sign = True

    group_by = 'client'

    columns = ['slug', 'title']
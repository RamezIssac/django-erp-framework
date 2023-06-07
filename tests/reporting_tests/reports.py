from django.utils.translation import gettext_lazy as _
from erp_framework.reporting.registry import register_report_view
from slick_reporting.forms import report_form_factory
from erp_framework.reporting.views import ReportView
from slick_reporting.generator import ReportGenerator
from .models import Client, SimpleSales, Product


@register_report_view
class ClientTotalBalance(ReportView):
    report_title = _("Clients Balances")

    # that's the report url endpoint
    # So this report ajax request will be sent reports/<namespace>/<report_slug>
    # this should be unique to the namespace
    report_slug = "balances"

    # here we define basic information for the report
    base_model = Client

    # Where is the data to compute
    report_model = SimpleSales
    group_by = "client"
    columns = ["slug", "name", "__balance__", "__total__"]
    chart_settings = [
        {
            "id": "pie",
            "name": _("pie"),
            "type": "pie",
            "data_source": ["__balance__"],
            "title_source": ["name"],
        },
    ]


@register_report_view
class ClientTotalBalancesOrdered(ClientTotalBalance):
    report_slug = None
    default_order_by = "__balance__"


@register_report_view
class ClientTotalBalancesOrderedDESC(ClientTotalBalance):
    report_slug = None
    default_order_by = "-__balance__"


@register_report_view
class ProductTotalSales(ReportView):
    report_title = _("Product Sales")

    # identifier of the report
    # This report ajax request will be sent reports/<namespace>/<report_slug>
    # `report_slug` should be unique to the namespace
    report_slug = "total_sales"

    # here we define basic information for the report
    base_model = Product

    # Where is the data to compute
    report_model = SimpleSales

    # here is the meat and potato of the report,
    # we group the records in SimpleSales by Client ,
    # And we display columns slug and name (relative to the `base_model` defined above)
    # the magic field `__balance__` computes the balance (of the base model)

    group_by = "product"
    columns = ["slug", "name", "__balance__", "__balance_quantity__"]
    swap_sign = True


@register_report_view
class ClientList(ReportView):
    report_title = _("Our Clients")

    # report_slug = 'client_list'
    base_model = Client
    report_model = SimpleSales

    hidden = True

    group_by = "client"
    columns = ["slug", "name"]


@register_report_view
class ProductClientSales(ReportView):
    base_model = Client
    report_model = SimpleSales

    report_slug = "client_sales_of_products"
    report_title = _("Client net sales for each product")
    must_exist_filter = "client_id"
    header_report = ClientList
    form_class = report_form_factory(report_model)

    group_by = "product"
    columns = ["slug", "name", "__balance_quantity__", "__balance__"]

    chart_settings = [
        {
            "id": "total_pie",
            "name": _("sales by client"),
            # 'settings': {
            "type": "pie",
            # 'name': _('sales for {product}'),
            "sub_title": _("{date_verbose}"),
            "data_source": ["__balance_quantity__"],
            "series_names": [_("Sales Qty")],
            # }
        },
        # {
        #     'id': 'total_bar',
        #     'name': _('sales by client (Bar)'),
        #     'settings': {
        #         'chart_type': 'column',
        #         'y_sources': ['__balance_quantity__'],
        #
        #         'name': _('sales for {product}'),
        #         'sub_title': _('{date_verbose}'),
        #         'series_names': [_('sales Qty')],
        #     }
        # },
    ]


@register_report_view
class ProductSalesMonthlySeries(ReportView):
    base_model = Product
    report_model = SimpleSales
    report_title = _("Product Sales Monthly")

    group_by = "product"
    columns = ["slug", "name"]
    time_series_pattern = ("monthly",)
    time_series_columns = ["__balance_quantity__", "__balance__"]

    chart_settings = [
        {
            "id": "movement_column",
            "name": _("comparison - column"),
            "type": "column",
            "chart_type": "column",
            "data_source": ["__balance__"],
        },
        {
            "id": "movement_line",
            "name": _("comparison - line"),
            "type": "line",
            "data_source": ["__balance__"],
            "title_source": "name",
        },
    ]


class ClientReportMixin:
    base_model = Client
    report_model = SimpleSales


@register_report_view
class ClientSalesMonthlySeries(ClientReportMixin, ReportView):
    report_title = _("Client Sales Monthly")
    base_model = Client
    report_model = SimpleSales

    group_by = "client"
    columns = ["slug", "name"]
    time_series_pattern = "monthly"
    time_series_columns = ["__debit__", "__credit__", "__balance__", "__total__"]


#


@register_report_view
class ClientDetailedStatement(ReportView):
    report_title = _("client statement")
    base_model = Client
    report_model = SimpleSales
    #
    # header_report = ClientList
    # must_exist_filter = 'client_id'

    group_by = None
    columns = ["slug", "date", "type", "product__name", "quantity", "price", "value"]


@register_report_view
class ClientDetailedStatement2(ReportView):
    report_title = _("client statement")
    base_model = Client
    report_model = SimpleSales

    header_report = ClientList
    must_exist_filter = "client_id"

    group_by = None
    columns = ["slug", "date", "type", "product__name", "quantity", "price", "value"]


@register_report_view
class ProductClientSalesMatrix(ReportView):
    base_model = Product
    report_model = SimpleSales
    report_title = _("Matrix")

    swap_sign = True

    group_by = "client"
    columns = ["slug", "name"]

    crosstab_field = "client"
    crosstab_columns = ["__total__"]


class GeneratorClassWithAttrsAs(ReportGenerator):
    columns = ["get_icon", "slug", "name"]


@register_report_view
class ClientTotalBalancesWithShowEmptyFalse(ClientTotalBalance):
    report_slug = None
    default_order_by = "-__balance__"
    show_empty_records = False

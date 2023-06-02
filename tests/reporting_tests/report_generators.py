from slick_reporting.generator import ReportGenerator
from .models import Order, OrderLine


class GenericGenerator(ReportGenerator):
    report_model = OrderLine
    date_field = "order__date_placed"

    # here is the meat and potatos of the report,
    # we group the sales per client , we display columns slug and name (of the `base_model` defied above
    # and we add the magic field `__balance__` we compute the client balance.
    group_by = "client"
    columns = ["slug", "name", "__balance__"]


class GeneratorWithAttrAsColumn(GenericGenerator):
    group_by = "client"

    columns = ["get_data", "slug", "name"]

    def get_data(self, obj):
        return ""

    get_data.verbose_name = "get_data_verbose_name"


class CrosstabOnClient(GenericGenerator):
    group_by = "product"
    columns = ["name", "__total_quantity__"]
    crosstab_field = "client"
    crosstab_columns = ["__total_quantity__"]

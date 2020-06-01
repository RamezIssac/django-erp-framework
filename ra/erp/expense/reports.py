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

    group_by = 'client'
    columns = ['slug', 'title', '__total__']
    chart_settings = [
        {
            'id': 'pie',
            'title': _('Expense Totals'),
            'type': 'pie',
            'data_source': '__balance__',
            'title_source': 'title',
        },
        {
            'id': 'bar',
            'title': _('Client Balances [Bar]'),
            'type': 'bar',
            'data_source': '__balance__',
            'title_source': 'title',
        },
    ]

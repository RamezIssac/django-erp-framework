from datetime import datetime

import pytz
from django.test import TestCase
from django.utils.timezone import now

from ra.reporting.generator import ReportGenerator
from .models import OrderLine


class GeneratorReportStructureTest(TestCase):
    def test_simple_report(self):
        x = ReportGenerator(OrderLine, date_field='order__date_placed', group_by='client', columns=['title'],
                            time_series_columns=['__total_quan__'], time_series_pattern='monthly',
                            start_date=datetime(2020, 1, 1, tzinfo=pytz.timezone('utc')),
                            end_date=datetime(2020, 12, 31, tzinfo=pytz.timezone('utc')))
        # import pdb;
        # pdb.set_trace()
        self.assertEqual(len(x.get_list_display_columns()), 13)

    def test_time_series(self):
        pass

    def test_cross_tab(self):
        pass

    def test_time_series_and_cros_tab(self):
        pass



# test that columns are a straight forward list

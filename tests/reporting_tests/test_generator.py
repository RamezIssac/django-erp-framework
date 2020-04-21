from datetime import datetime

import pytz
from django.test import TestCase
from django.utils.timezone import now

from ra.reporting.generator import ReportGenerator
from .models import OrderLine

from .report_generators import GeneratorWithAttrAsColumn, CrosstabOnClient

from .tests import BaseTestData


class MatrixTests(BaseTestData, TestCase):
    def test_matrix_column_included(self):
        report = CrosstabOnClient(crosstab_ids=[self.client1.pk], crosstab_compute_reminder=False)
        columns = report.get_list_display_columns()
        self.assertEqual(len(columns), 3, columns)

        report = CrosstabOnClient(crosstab_ids=[self.client1.pk], crosstab_compute_reminder=True)
        columns = report.get_list_display_columns()
        self.assertEqual(len(columns), 4, columns)

    def test_get_crosstab_columns(self):
        report = CrosstabOnClient(crosstab_ids=[self.client1.pk])
        columns = report.get_list_display_columns()
        self.assertEqual(len(columns), 4)

        report = CrosstabOnClient(crosstab_ids=[self.client1.pk, self.client2.pk],
                                  crosstab_columns=['__total_quan__', '__balance_quan__'])
        columns = report.get_list_display_columns()
        self.assertEqual(len(columns), 8, [x['name'] for x in columns])


class GeneratorReportStructureTest(TestCase):
    def test_time_series_columns_inclusion(self):
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

    def test_attr_as_column(self):
        report = GeneratorWithAttrAsColumn()
        columns_data = report.get_list_display_columns()
        self.assertEqual(len(columns_data), 3)

        self.assertEqual(columns_data[0]['verbose_name'], 'get_data_verbose_name')

    def test_improper_group_by(self):
        def load():
            ReportGenerator(OrderLine, group_by='no_field', date_field='order__date_placed')

        self.assertRaises(Exception, load)

    def _test_attr_called(self):
        report = GeneratorWithAttrAsColumn()
        data = report.get_report_data()
        # self.assertEqual(len(report.get_list_display_columns()), 3)

# test that columns are a straight forward list

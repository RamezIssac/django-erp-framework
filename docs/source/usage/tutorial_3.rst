Tutorial (Part 3) - Creating Time series and Crosstab Reports
-------------------------------------------------------------


In this section we will create time series report and crosstab report with charts.

First let's recap what we did in Part 2

1. We created a `reports.py` in which we organised our report classes
2. we explored crating a report by inheriting from a `ReportView`class and assign the needed attributes.
3. we got introduced to the report fields like `__balance__` and `__balance_quan__` , and that they compute the needed values.
4. we got introduced to the a 2 layer report and introduced to charts.

Time Series
~~~~~~~~~~~
It's a report where the columns represents time unit (year/month/week/day)


Let's see an example


.. code-block:: python

    @register_report_view
    class ProductSalesMonthlySeries(ReportView):
        report_title = _('Product Sales Monthly')

        base_model = Product
        report_model = SimpleSales

        form_settings = {
            'group_by': 'product',
            'group_columns': ['slug', 'title'],

            # how we made the report a time series report
            'time_series_pattern': 'monthly',
            'time_series_fields': ['__balance__'],
        }


We just added ``time_series_pattern`` which describe which pattern you want to compute (more pattern :ref:`time_series_pattern`)
and ``time_series_fields`` where we indicated on which field to compute in this time series.

Noticed that ``time_series_fields`` is a list, which means that we can have more fields computed.
In the above report, we knew the value of sales for each product in each month, We can also know how much units sold each month as well.
Add `__balance_quan__` in the `time_series_fields`.


.. code-block::python

    @register_report_view
    class ProductSalesMonthlySeries(ProductReportMixin, ReportView):
        ...
        form_settings = {
            ...
            'time_series_pattern': 'monthly',
            'time_series_fields': ['__balance_quan__', '__balance__'],

        }

Reload your app and check the results. You should see that for each month, we have 2 fields "Balance QTY" and "Balance"


Now let's add some charts, shall we ?

.. code-block:: python

    # Add chart settings to your ProductSalesMonthlySeries
    @register_report_view
    class ProductSalesMonthlySeries(ReportView):
        ...
        chart_settings = [
                {
                    'id': 'column_chart',
                    'title': _('comparison - column'),
                    'settings': {
                        'chart_type': 'column',
                        'title': _('Product sales monthly '),
                        'sub_title': _('{date_verbose}'),
                        'y_sources': ['__balance__'],
                        'series_names': [_('Sales value')],
                    }
                },
                {
                    'id': 'movement_line',
                    'title': _('comparison - line'),
                    'settings': {
                        'chart_type': 'line',
                        'title': _('Product sales monthly '),
                        'sub_title': _('{date_verbose}'),
                        'y_sources': ['__balance__'],
                        'series_names': [_('Sales value')],
                    }
                },
            ]



You can now create a time series report for client sales on your own.
We encourage you to try and do it by yourself and then comeback and compare what you wrote to our code.

.. code-block:: python

    @register_report_view
    class ClientSalesMonthlySeries(ClientReportMixin, ReportView):
        report_title = _('Client Sales Monthly')

        base_model = Client
        report_model = SimpleSales

        form_settings = {
            'group_by': 'client',
            'group_columns': ['slug', 'title'],

            'time_series_pattern': 'monthly',
            'time_series_fields': ['__balance__'],
        }
Notice that in this report we didnt use `__balance_quan__`, We can't aggregate quantity of different products.


Cross-tab report
~~~~~~~~~~~~~~~~

.. code-block:: python

    @register_report_view
    class ProductClientSalesMatrix(ReportView):
        base_model = Product
        report_model = SimpleSales
        report_title = _('Product Client sales Cross-tab')

        form_settings = {
            'group_by': 'product',
            'group_columns': ['slug', 'title'],

            # cross tab settings
            'matrix': 'client',
            'matrix_columns': ['__total__'],

            # custom name for the field
            'matrix_columns_names': {
                '__total__': _('movement')
            },
        }

        # sales decreases our product balance, accounting speaking,
        # but for reports sometimes we need the value sign reversed.
        swap_sign = True


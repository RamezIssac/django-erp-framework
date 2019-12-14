Tutorial (Part 3) - Creating Time series and Crosstab Reports
-------------------------------------------------------------


In this section we will create time series report and crosstab report with charts.

First let's recap what we did in Part 2

1. We created a `reports.py` in which we organised our ``ReportView`` classes and we made sure to import it in the `AppConfig.ready()`
2. we explored ``ReportView`` class needed attributes like base_model, report model, form_settings
3. we got introduced to the report fields like `__balance__` and `__balance_quan__` , and that they compute the needed values.
4. we got introduced to the a 2 layer report, also a report with no group where it displays the records directly.
5- We created charts using ``chart_settings``

Time Series
~~~~~~~~~~~

A time series is a report where the columns represents time unit (year/month/week/day)

Let's see an example


.. code-block:: python

    @register_report_view
    class ProductSalesMonthly(ReportView):
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


Reload your development server , go to Product reports, and check the Product Sales Monthly report.

All we did was adding

* ``time_series_pattern`` which describe which pattern you want to compute (daily/monthly/yearly)\
* ``time_series_fields`` where we indicated on which field to compute in this time series.

Noticed that ``time_series_fields`` is a list, which means that we can have more fields computed in the time series.

In the above report, we knew the sum of *value* of sales for each product, in each month, We can also know the sum of *quantity* of each product sold each month as well.

Add ``'__balance_quan__'`` to the ``time_series_fields`` list,


.. code-block::python

    @register_report_view
    class ProductSalesMonthlySeries(ProductReportMixin, ReportView):
        ...
        form_settings = {
            ...
            'time_series_pattern': 'monthly',
            'time_series_fields': ['__balance_quan__', '__balance__'],

        }

        swap_sign = True
* swap_sign will do as the name suggest. Why results are negative in the first place ? Remember `sales` doc_type is registered to "minus" Product and this is *modeling* from accounting.

Reload your app and check the results. You should see that for each month, we have 2 fields "Balance QTY" and "Balance"


Now let's add some charts, shall we ?

.. code-block:: python

    # Add chart settings to your ProductSalesMonthlySeries
    @register_report_view
    class ProductSalesMonthlySeries(ReportView):
        ...
        chart_settings = [
            {
                'id': 'movement_bar',
                'title': _('comparison - Bar - Stacked'),
                'data_source': '__balance__',
                'title_source': 'product__title',
                'type': 'bar',
                'stacked': True,
            },
            {
                'id': 'movement_column_ns',
                'title': _('comparison - Bar'),
                'data_source': '__balance__',
                'title_source': 'product__title',
                'type': 'bar',
                'stacked': False,
            },

            {
                'id': 'movement_column_total',
                'title': _('comparison - Bar - Total'),
                'data_source': '__balance__',
                'title_source': 'product__title',
                'type': 'bar',
                'plot_total': True,
            },

            {
                'id': 'movement_line_stacked',
                'title': _('comparison - line - Stacked'),
                'data_source': '__balance__',
                'title_source': 'product__title',
                'type': 'line',
                'stacked': True,
            },

            {
                'id': 'movement_line',
                'title': _('comparison - line'),
                'data_source': '__balance__',
                'title_source': 'product__title',
                'type': 'line',
            },
            {
                'id': 'movement_line_total',
                'title': _('comparison - line - Total'),
                'data_source': '__balance__',
                'title_source': 'product__title',
                'type': 'line',
                'plot_total': True,
            },
        ]

6 charts to highlight the patterns. Reload the development server and *the report page* and check the output.

The charts brings our attention that the slops are always rising ... that's because we're using the __balance__ report field. which is a *compound* total of the sales.
In fact here, we might be more interested in the *non* compound total, and there is a report field for that that comes by default called ``__total__``

Let's change ``__balance__`` with ``__total__`` and check the results.

You can now create a time series report for the Client sales per month Yeah ?

It would look like something like this

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

You can add charts to this report too !


Cross-tab report
~~~~~~~~~~~~~~~~

A cross tab report is when the column represents another different named data object


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

        }

        # sales decreases our product balance, accounting speaking,
        # but for reports sometimes we need the value sign reversed.
        swap_sign = True

Lke with the time series pattern, we added

1- ``matrix``: the field to use as comparison column
2. ``matrix_column`` the report field we want to compare per the crosstab .
3- we used ``__total__`` report field.

   Example:

   If total Sales are 10, 15, 20 for the months January to March respectively, balance For those 3 month would be 10, 25, 45.



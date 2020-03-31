Creating Reports (Part2)
------------------------

First Let's recap what we did so far.

1. We created a `Product`, `Client` and `SimpleSales` models, created and registered a *doc_type*;
2. We created ModelAdmin classes inheriting from `RaAdmin` and `RaMovement` for our classes;
3. We created a custom template extending from `RA_THEME|add:'/changeform.html'`, and we used `smartParseFloat` to deal with numbers on front end.

Now let's create some reports!!
We would like to know
    1. How much each Client bought (in value).
    2. How much each Product is Sold (In value and in quantity)
    3. For each client, the total bought of each product
    4. A Client statement

Then we will be adding charts

How much each Client bought (in value)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In our sales app, let's create a `reports.py` file *it can be any name, this is just a convention*

.. code-block:: python

    from django.utils.translation import ugettext_lazy as _
    from ra.reporting.decorators import register_report_view
    from ra.reporting.views import ReportView
    from .models import Client, SimpleSales


    @register_report_view
    class ClientTotalBalance(ReportView):
        report_title = _('Clients Balances')

        base_model = Client
        report_model = SimpleSales

        form_settings = {'group_by': 'client',
                         'group_columns': ['slug', 'title', '__balance__']}

Now we need to import `reports.py` so our code is executed.
Best way to do such action is in `AppConfig.ready <https://docs.djangoproject.com/en/2.2/ref/applications/#django.apps.AppConfig.ready>`_

.. code-block:: python

    # in sales __init__.py
    default_app_config = 'sales.apps.SalesConfig'

    # in sales/apps.py
    from django.apps import AppConfig


    class SalesConfig(AppConfig):
        name = 'sales'

        def ready(self):
            super().ready()
            from . import reports


Above is fairly django standard, you can read more on Apps `on Django's documentation <https://docs.djangoproject.com/en/2.2/ref/applications/#configuring-applications>`_


Now re-run `runserver`, go to to the dashboard, You'll find a new menu **Reports** which would contains a *Client* sub menu.
Click on the Clients menu will open the Client Report List, which will load the first report automatically.

We can notice that

1. Report table is sortable and searchable (Thanks to `datatables.net <https://datatables.net/>`_ )
2. Client's name and slug/refer code are clickable and will direct you to Statistics of that client, *we will be filling this page later in :ref:`adding_charts_widgets`
3. There is a dedicated sub page for printing (More about Customizing prints later )
4. Report can also be exported to Excel.
5. You can filter by *Date* , *Client* and *Product*. For the later two, the widget allow you to select multiple objects.
6. All filters and calculation are done automatically.

Let's create another report that answers the question

How much each product was sold?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


.. code-block:: python

    from .models import Product

    @register_report_view
    class ProductTotalSales(ReportView):
        # Title will be displayed on menus, on page header etc...
        report_title = _('Product Sales')

        # What model is this report about
        base_model = Product

        # What model hold the data that we want to compute.
        report_model = SimpleSales

        # The meat and potato of the report.
        # We group the records in SimpleSales by Client ,
        # And we display the columns `slug` and `title` (relative to the `base_model` defined above)
        # the magic field `__balance__` computes the balance (of the base model)
        form_settings = {'group_by': 'product',
                         'group_columns': ['slug', 'title', '__balance__']}

Did you notice that both class definition are almost the same.
Only differences are the `base_model` and in `form_settings.group_by`.

Basically, to create a report we need:

1. Give it a title (obviously)
2. Assign ``base_model`` and ``report_model``
3. Depending on what data we want, we need to fill ``form_settings``

For more information about available option in form_settings :ref:`reporting`

Now let's create a 3rd report.

.. _header_report_tutorial:
How much each client bought of each product ?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

But wait a minute, how will we display this report, so far all reports we created were only 1 level, now we need 2.
Level 1 would display a list of clients, level 2 display the sum of the sales for each product for that client.

Let's add this code to our `reports.py`

.. code-block:: python

    @register_report_view
    class ClientList(ReportView):
        report_title = _('Our Clients')

        base_model = Client
        report_model = SimpleSales

        # will not appear on the reports menu
        hidden = True

        form_settings = {
            'group_by': 'client',
            'group_columns': ['slug', 'title'],

            # adds + sign in the start of the report table
            'add_details_control': True,
        }


    @register_report_view
    class ProductClientSales(ReportView):
        report_title = _('Client Sales for each product')

        base_model = Client
        report_model = SimpleSales

        must_exist_filter = 'client_id'
        header_report = ClientList

        form_settings = {
            'group_by': 'product',
            'group_columns': ['slug', 'title', '__balance_quan__', '__balance__'],
        }


Let's run this code and see what it did then we will analyze it.

You should find "Client Sales for each Product" as new report, it should display a list of clients;
Clicking on the "+" sign, and it should open a popup with the a table of the products displaying a the total value and the total *quantity* sold by each product for the chosen clients.

Let's analyze what we just did:

We created 2 report view classes

* ``ClientList`` ReportView class, creates that first layer, It serves to only displays the list of client from which will select.
* ``ProductClientSales`` which contain couple of new stuff

    * `must_exists_filter` and `header_report` are what allow this report to display the `ClientList` *the header_report* as long as the *must_exists_filter* is not in the querystring.
    * The new computation field ``__balance_quan__`` which operate on the `quantity` field, *where `__balance__` operates on the `value` field.


Now for the final report in this this section.

A Client Detailed statement.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Which is a simple list of the sales transaction


.. code-block:: python

    @register_report_view
    class ClientDetailedStatement(ReportView):
        report_title = _('client Statement')
        base_model = Client
        report_model = SimpleSales

        must_exist_filter = 'client_id'
        header_report = ClientList

        form_settings = {
            'group_columns': ['slug', 'doc_date', 'doc_type', 'product__title', 'quantity', 'price', 'value'],
        }

.. _adding_charts_tutorial:

Adding Charts
~~~~~~~~~~~~~~

Default Charts library used on front end `Charts.js <https://www.chartjs.org/>`_ Open source HTML5 Charts.

To add charts to a report, you'd need to add to ``chart_settings`` .
Here is an example we will add two charts to teh first report we created `ClientTotalBalance`

.. code-block:: python

    class ClientTotalBalances(ReportView):
        ...
        chart_settings = [
            {
                'id': 'pie_chart',
                'type': 'pie',
                'title': _('Client Balances'),
                'data_source': '__balance__',
                'title_source': 'client__title',
            },
            {
                'id': 'bar_chart',
                'type': 'bar',
                'title': _('Client Balances [Bar]'),
                'data_source': '__balance__',
                'title_source': 'client__title',
            },
        ]

Reload your development server and check how those charts are displayed in the Client Balances report.

Neat right ?

So to create a report we need to a dictionary to a ``chart_settings`` list containing

* id: how we would refer to this exact chart in front end (we will use that in :ref:`adding_charts_widgets`
* type: what kind of chart it is bar , pie, line
* data_source: Field name of containing the numbers we want to chart,
* title_source: Field name of containing the labels of those numbers
* title: the chart title

FOr Other settings available, see :ref:`charts_configuration`

In the next section we will create even more interesting reports types like

1. Time Series: We want to know how much each product was sold, per month.
3. Crosstab product sales to clients (or the opposite).

Keep on reading !









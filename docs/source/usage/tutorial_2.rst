Tutorial (Part 2) - Creating Reports
-------------------------------------

First Let's recap what we did so far.

1. We created a `Product`, `Client` and `SimpleSales` models, created and registered a *doc_type*;
2. We created ModelAdmin classes inheriting from `RaAdmin` and `RaMovement` for our classes;
3. We created a custom template extending from `ra/admin/changeform.html`, and we used `smartParseFloat` to deal with numbers.

Now let's create some reports
We want to know
    How much each Client bought (in value)
    How much each Product is Sold
    for each client, the total bought of each product


In our ra_demo app, let's create a `reports.py` file *it can be any name, this is just a convention*

.. code-block:: python

    from django.utils.translation import ugettext_lazy as _
    from ra.reporting.decorators import register_report_view
    from ra.reporting.views import ReportView
    from .models import Client, SimpleSales


    @register_report_view
    class clientTotalBalance(ReportView):
        report_title = _('Clients Balances')

        base_model = Client
        report_model = SimpleSales

        form_settings = {'group_by': 'client',
                         'group_columns': ['slug', 'title', '__balance__'],
                         }

Now we need to import `reports.py` so our code is executed. Best way to do such action is in AppConfig.ready (ref to django docs).
Since this app was created by `start` command `reports.py` is already imported in the app ready handler.

Now re-run `runserver`, goto to the dashboard, You'll find a new menu **Reports** which would contains a *Client* sub menu.
Click on the Clients menu will open the Client Report List, which will load the first report automatically.

We can draw your attention to:

1. Report table is sortable, and searchable (Thanks to Datatables.net)
2. Client's name and slug/refer code is clickable and will direct you to Statistics of that client, we will be filling this page later in the tutorial.
3. There is a dedicated sub page for printing (More about Customizing prints here )
4. Report can also be exported to Excel
5. You have filters for *Date* , for *Client* and for *Product*

Notice that the Framework did all the calculation, and apply all filters automatically. Try changing dates, selecting, a client and/or a product and hitting Refresh.


Let's create another report that answers the question **How much each product was sold?**

.. code-block:: python

    @register_report_view
    class ProductTotalSales(ReportView):
        # Title will be displayed on menus, on page header etc...
        report_title = _('Product Sales')

        # What model is this report about
        base_model = Product

        # WHat model hold the data that we want to compute on
        report_model = SimpleSales

        # The meat and potato of the report.
        # We group the records in SimpleSales by Client ,
        # And we display the columns `slug` and `title` (relative to the `base_model` defined above)
        # the magic field `__balance__` computes the balance (of the base model)
        form_settings = {'group_by': 'product',
                         'group_columns': ['slug', 'title', '__balance__'],
                         }

Did yo notice that both class definition is almost the same.
Differences are the `base_model` and in `form_settings.group_by`.

For more information about form_settings ref `advanced_topics/report_form_settings.rst`

Now let's create a 3rd report !

How much each client bought of each product ?
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

            # adds the + sign in the start of the report table
            'add_details_control': True,
        }


    @register_report_view
    class ProductClientSales(ReportView):
        report_title = _('Client Sales for each product')

        base_model = Client
        report_model = SimpleSales

        must_exist_filter = 'client_id'
        header_report = ClientList

        form_class = report_form_factory(report_model, base_model)

        form_settings = {
            'group_by': 'product',
            'group_columns': ['slug', 'title', '__balance_quan__', '__balance__'],
        }
        chart_settings = [
            {
                'id': 'total_pie',
                'title': _('sales by client'),
                'settings': {
                    'chart_type': 'pie',
                    'y_sources': ['__balance_quan__'],

                    'title': _('sales for {product}'),
                    'sub_title': _('{date_verbose}'),
                    'series_names': [_('sales Qty')],
                }
            },

            {
                'id': 'total_bar',
                'title': _('sales by client (Bar)'),
                'settings': {
                    'chart_type': 'bar',
                    'y_sources': ['__balance_quan__'],

                    'title': _('sales for {product}'),
                    'sub_title': _('{date_verbose}'),
                    'series_names': [_('sales Qty')],
                }
            },

        ]



Let's run this code and see what it did then we will analyze it.

You should find "Client Sales for each Product" as new report, it should display a list of clients;
Clicking on the "+" sign, and it should open a popup with the a table of the products *(and a chart)* displaying a the total value and the total *quantity* sold by each product for the chosen clients.

Let's analyze our code:

We created 2 report view classes

* ``ClientList`` ReportView class, creates that first layer, It serves to only displays the refer code and the name, from which we select a client.
* ``ProductClientSales`` which contain many of the interesting stuff, notice the following

    * `must_exists_filter` and `header_report` are what allow this report to display the `ClientList` *the header_report* as long as the *must_exists_filter* is not there is the querystring.
    * `form_class = report_form_factory(report_model, base_model)`
      ``report_form_factory`` is the utility responsible for creating the report form which contains the filters you see like date, client and product.
    * The new computation field ``__balance_quan__`` which operate on the `quantity` field, *where `__balance__` operates on the `value` field.
    * Charts Configuration

.. note::
    Basically ``report_form_factory`` will scan your ``report_model`` for foreign keys and display them as filters.
    It will also include the date filter (from , to, or on exact date)
    This method can be further fine tuned, you can also <create your own form report>


.. hint::
    For more information on chart types and their configuration please refer to :ref:`charts_configuration`


Before we finish this section we can create a final easy report. Detailed statement.
a simple list of the sales transaction


.. code-block:: python

    @register_report_view
    class ClientDetailedStatement(ReportView):
        report_title = _('client Statement')
        base_model = Client
        report_model = SimpleSales

        form_settings = {
            'group_by': '',
            'group_columns': ['slug', 'doc_date', 'doc_type', 'product__title', 'quantity', 'price', 'value'],
        }

Check the results on your browser, filter by client and hit refresh to update teh results.

How about we add a *header_report* to this one, it would be nicer, yeah ?!

.. code-block:: python

    @register_report_view
    class ClientDetailedStatement(ReportView):
        ...

        header_report = ClientList
        must_exist_filter = 'client_id'

In the next section we will create more interesting reports.

1. We want to know how much each product was sold, per month.
2. Same for the client, how much was their sales, per month.
3. Crosstab product sales to clients (or the opposite).

Keep on reading !









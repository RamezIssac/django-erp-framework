Reporting and Charting
----------------------

We released our reporting engine as a standalone package (so can use it without being tied down to any of this)

Django slick reporting

We will talk generally here but for more detailed information, please head to Django Slick Reporting docs


Generating test data
~~~~~~~~~~~~~~~~~~~~

Before we begin, charts and reporting get more fun and interesting the more data available.
So below, a `custom management command <https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/>`_ code that you can use to generate data for the whole current year.
This will definitely enhance your experience with this next section. Also we will be using it for benchmarking Ra Performance.

Create and add below code to 'sales/management/commands/generate_data.py'

.. code-block:: python

    import random
    import datetime
    import pytz
    from django.core.management import BaseCommand


    class Command(BaseCommand):
        help = 'Generates data for simple sales app'

        def add_arguments(self, parser):
            parser.add_argument('--clients', type=int, action='store', help='Number of client to get generated, default 10')
            parser.add_argument('--product', type=int, action='store',
                                help='Number of products t0o get generated, default 10')
            parser.add_argument('--expenses', type=int, action='store',
                                help='Number of Expense to get generated, default 10')

            parser.add_argument('--expense-transaction', type=int, action='store',
                                help='Number of records per day,  default 10')

        def handle(self, *args, **options):
            from ...models import Client, Product, SalesTransaction, SalesLineTransaction, Expense, ExpenseTransaction
            from django.contrib.auth.models import User
            user_id = User.objects.first().pk
            client_count = options.get('clients', 10) or 10
            product_count = options.get('products', 10) or 10
            records_per_day = options.get('records', 10) or 10

            expense_count = options.get('expenses', 10) or 10
            etransaction_per_day = options.get('expense-transaction', 3) or 3

            # Generating clients
            already_recorded = Client.objects.all().count()
            clients_needed = client_count - already_recorded
            if clients_needed > 0:
                for index in range(already_recorded, already_recorded + clients_needed):
                    Client.objects.create(title=f'Client {index}', lastmod_user_id=user_id)
                self.stdout.write(f'{clients_needed} client(s) created')

            # Product
            already_recorded = Product.objects.all().count()
            product_needed = product_count - already_recorded
            if product_needed > 0:
                for index in range(already_recorded, already_recorded + product_needed):
                    Product.objects.create(title=f'Product {index}', lastmod_user_id=user_id)
                self.stdout.write(f'{product_needed} product(s) created')

            already_recorded = Expense.objects.all().count()
            Expenses_needed = expense_count - already_recorded
            if Expenses_needed > 0:
                for index in range(already_recorded, already_recorded + Expenses_needed):
                    Expense.objects.create(title=f'Expense {index}', lastmod_user_id=user_id)
                self.stdout.write(f'{Expenses_needed} Expense(s) created')

            # generating sales
            # we will generate 10 records per day for teh whole current year
            sdate = datetime.datetime(datetime.date.today().year, 1, 1)
            edate = datetime.datetime(datetime.date.today().year, 12, 31)

            client_ids = Client.objects.values_list('pk', flat=True)
            product_ids = Product.objects.values_list('pk', flat=True)
            expense_ids = Expense.objects.values_list('pk', flat=True)

            delta = edate - sdate  # as timedelta
            for i in range(delta.days + 1):
                day = sdate + datetime.timedelta(days=i)
                day = pytz.utc.localize(day)
                for z in range(1, records_per_day):
                    chosen_client = random.choice(client_ids)
                    SalesLineTransaction.objects.create(
                        doc_date=day,
                        sales_transaction=SalesTransaction.objects.create(doc_date=day, client_id=chosen_client,
                                                                          lastmod_user_id=user_id),
                        product_id=random.choice(product_ids),
                        client_id=chosen_client,
                        quantity=random.randrange(1, 10),
                        price=random.randrange(1, 10),
                        lastmod_user_id=user_id
                    )

                for z in range(1, etransaction_per_day):
                    ExpenseTransaction.objects.create(
                        doc_date=day,
                        expense_id=random.choice(expense_ids),
                        value=random.randrange(1, 10),
                        lastmod_user_id=user_id
                    )
                self.stdout.write(f'{day} Done')
                self.stdout.flush()

            self.stdout.write('----')
            self.stdout.write('Done')

Then let's run the command

.. code-block:: console

    $ python manage.py generate_data

    # and here with the default arguments in case you want to fine tune
    $ python manage.py generate_data --clients 10 --products 10 --records 10 --expense 10 --expense-transaction 3


Now we have some test data to give us a more complete look. Let's create some reports!!

Sample Reports
~~~~~~~~~~~~~~

We would like to know

    1. How much each Client bought (in value).
    2. How much each Product is Sold (In value and in quantity)
    3. For each client, how much they bought of each product
    4. A Client detailed statement

Then we will be adding charts

How much each Client bought (in value)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In our `sample_erp` app, let's create a `reports.py` file *it can be any name, this is just a convention*

.. code-block:: python

    from django.utils.translation import ugettext_lazy as _
    from ra.reporting.registry import register_report_view
    from ra.reporting.views import ReportView
    from .models import Client, SalesLineTransaction, Product


    @register_report_view
    class ClientTotalBalance(ReportView):
        report_title = _('Clients Balances')

        base_model = Client
        report_model = SalesLineTransaction

        group_by = 'client'
        columns = ['slug', 'title', '__balance__']


Now we need to load `reports.py` during the app life cycle so our code is executed. Best way to do such action is in `AppConfig.ready <https://docs.djangoproject.com/en/2.2/ref/applications/#django.apps.AppConfig.ready>`_

.. code-block:: python

    # in sample_erp __init__.py
    default_app_config = 'sample_erp.apps.SampleERPConfig'

    # in sales/apps.py
    from django.apps import AppConfig


    class SampleErpConfig(AppConfig):
        name = 'sample_erp'

        def ready(self):
            super().ready()
            from . import reports


Above is fairly django standard, you can read more on Apps `on Django's documentation <https://docs.djangoproject.com/en/2.2/ref/applications/#configuring-applications>`_


Now re-run `runserver`, go to to the dashboard, You'll find a new menu **Reports** which would contains a *Client* sub menu.
Click on the Clients menu will open the Client Report List, which will load the first report automatically.

We can notice that

1. Report table is sortable and searchable (Thanks to `datatables.net <https://datatables.net/>`_ )
2. Report can also be exported to Excel, can also be printed with a dedicated html template
3. You can filter by *Date* , *Client* and *Product*. For the later two, the widget allow you to select multiple objects.
4. All filters and calculation are done automatically.

Let's create another report that answers the following question

How much each product was sold?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


.. code-block:: python

    @register_report_view
    class ProductTotalSales(ReportView):
        # Title will be displayed on menus, on page header etc...
        report_title = _('Product Sales')

        # What model is this report about
        base_model = Product

        # What model hold the data that we want to compute.
        report_model = SalesLineTransaction

        # The meat and potato of the report.
        # We group the records in SimpleSales by Client ,
        # And we display the columns `slug` and `title` (relative to the `base_model` defined above)
        # the magic field `__balance__` computes the balance (of the base model)
        group_by = 'product'
        columns = ['slug', 'title', '__balance_quantity__']

Did you notice that both class definition are almost the same.
Main differences are the `base_model` and in `group_by` and we used `__balance_quantity__` which summarize the field "quantity" instead of the field "value".

For more information about available options checkout the Django Slick Reporting documentation `Here <https://django-slick-reporting.readthedocs.io/en/latest/>`_

Now let's create a 3rd report.

A Client Detailed statement.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Which is a simple list of the sales transaction

.. code-block:: python

    @register_report_view
    class ClientDetailedStatement(ReportView):
        report_title = _('client Statement')
        base_model = Client
        report_model = SalesLineTransaction


        columns = ['slug', 'doc_date', 'doc_type', 'product__title', 'quantity', 'price', 'value']


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
                'title_source': 'title',
            },
            {
                'id': 'bar_chart',
                'type': 'bar',
                'title': _('Client Balances [Bar]'),
                'data_source': '__balance__',
                'title_source': 'title',
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









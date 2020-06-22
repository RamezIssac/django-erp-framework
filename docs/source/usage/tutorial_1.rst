Part 1: Create a sales application
==================================

Let's use the project we just generated in the Quickstart section and build an app that records and report product sales to clients.

First we need to create an app

.. code-block:: console

    $ django-admin startapp sales

then add `sales` to your ``INSTALLED_APPS``.

Models
------

To track product sales to clients, we would need 3 models. Client, Product and A Sales Transaction model. Yeah? Let's create them in our `models.py`

.. code-block:: python

    from django.db import models
    from ra.base.models import EntityModel, TransactionModel, QuantitativeTransactionItemModel
    from ra.base.registry import register_doc_type
    from django.utils.translation import ugettext_lazy as _


    class Product(EntityModel):
        class Meta:
            verbose_name = _('Product')
            verbose_name_plural = _('Products')


    class Client(EntityModel):
        class Meta:
            verbose_name = _('Client')
            verbose_name_plural = _('Clients')


    class SimpleSales(QuantitativeTransactionItemModel):
        client = models.ForeignKey(Client, on_delete=models.CASCADE)
        product = models.ForeignKey(Product, on_delete=models.CASCADE)

        @classmethod
        def get_doc_type(cls):
            return 'sales'

        class Meta:
            verbose_name = _('Sale')
            verbose_name_plural = _('Sales')



Two things are worth highlighting here

1. The Base Classes from which we subclassed the Client, Product and SimpleSales models.
   Ra comes with a set a `Base Classes` that orchestrate and the system integration, you can read more about :ref:`base_classes`.
   Among other things, they provides fields like creator and last modified by, slug and notes.

   | **EntityModel**: is the Base class from which all other base classes are derived.
   | **QuantitativeTransactionItemModel**: is the base class of a transaction and provide useful fields usually needed for any transaction, like `refer_code`, `doc_date` , `quantity` , `price`, `discount` and `value`


Run ``python manage.py makemigrations sales``, then
``python manage.py migrate`` to update the database with your model

The Admin
----------

Ra makes use of the django admin to leverage the process of authentication, authorization and CRUD operation(s).

This a great because this gives you an easier learning curve. If you know Django admin you'd easily find your way around EntityAdmin
With this information in mind, let's add this piece of code into `admin.py`

.. code-block:: python

    from ra.admin.admin import ra_admin_site, EntityAdmin, TransactionAdmin
    from .models import Client, Product, SimpleSales

    class ClientAdmin(EntityAdmin):
        pass


    class ProductAdmin(EntityAdmin):
        pass


    class SalesOrderAdmin(TransactionAdmin):
        fields = ['slug', 'doc_date', 'client', ('product', 'price', 'quantity', 'value')]


    ra_admin_site.register(Client, ClientAdmin)
    ra_admin_site.register(Product, ProductAdmin)

    # we could have just..
    # ra_admin_site.register(Client, EntityAdmin)
    # ra_admin_site.register(Product, EntityAdmin)
    # .. but we will need them later :)

    ra_admin_site.register(SimpleSales, SalesOrderAdmin)


Like with models, here we inherit our admin models from ``EntityAdmin`` and ``TransactionAdmin``.
Also we register our model with their AdminModel with ``ra_admin_site`` which is an independent admin site than the default django one.

.. note::

    EntityAdmin and TransactionAdmin are just subclasses of admin.ModelAdmin. You can customize it as you'd do normally with any ModelAdmin.
    You can add list_filter, make the foreign key widget to be Select2, adjust which fields and teh fieldsets on the change_form etc.

Read more about :ref:`ra_admin`

Let's run and access our Dashboard, enter your username and password already created with `createsuperuser`.
In the left hand menu you'd find a menu, which will contains links to Clients, Products & SimpleSales admin pages as you'd expect.


Go to the sales order page, add a couple of sale transaction entries.
Now, we notice that *value field* is editable,  it should be read only and equal to result of multiplying price and quantity and this should be done automatically.

Front End customization
-----------------------

Let's enhance our Sales Page and make `value` a read only and compute it on the front end and display it to the user.
To do that we need to add a little javascript to handle the client side calculation, and to do that we'll need a create our own template.

In your `sales` app directory, create a `templates` folder, and inside it you can create
a template file `sales/admin/salesorder_changeform.html` and in it we can write:

.. code-block:: Django

    {% extends 'ra/base_site.html' %}

    {% block admin_change_form_document_ready %}
        <script>
            $(document).ready(function () {
                const $quantity = $('[name*=quantity]');
                const $price = $('[name*=price]');

                function calculateTotal(e) {
                    let quantity = $.ra.smartParseFloat($quantity.val());
                    let price = $.ra.smartParseFloat($price.val());
                    $('[name*=value]').val(quantity * price)
                }

                $quantity.on('change', calculateTotal);
                $price.on('change', calculateTotal);
            })
        </script>
    {% endblock %}

Notice here:

1. we `extends` from `ra/base_site.html'`
   This enables us to change themes of your Ra dashboard rather easily. You can read more about :ref:`theming`

2. we use :func:`$.ra.smartParseFloat` in the javascript.
   This is a custom convenience function to handle strings or empty value when numbers are expected (in which case `value` result would be `NaN`.
   If you want to try just replace smartParseFloat with normal `parseFloat` and enter a string or make empty the quantity and/or price field.

   For list of javascript tools available :ref:`javascript`

Now we attach this template to our admin model class, and make the value field readonly.

.. code-block:: python

    from django import forms

    class SalesOrderAdmin(TransactionAdmin):
        ...

        add_form_template = change_form_template = 'sales/admin/salesorder_changeform.html'

        def formfield_for_dbfield(self, db_field, request, **kwargs):
            formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
            if db_field.name == 'value':
                formfield.widget = forms.TextInput(attrs={'readonly': 'readonly'})
            return formfield

Now runserver, go to Sales Order and check the outcome, experiment around and add some of sales records, those records will be useful in our next section.
Next Section we will create interesting reports about product sales, which product being bought by which clients and client total sales.

Reports
~~~~~~~~

Before we begin, charts and reporting get more fun and interesting the more data available.
So below, a `custom management command <https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/>`_ code that you can use to generate data for the whole current year.
This will definitely enhance your experience with this next section. Also we will be using it for benchmarking Ra Performance.


Generating test data
~~~~~~~~~~~~~~~~~~~~
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
            parser.add_argument('--products', type=int, action='store',
                                help='Number of products to get generated, default 10')
            parser.add_argument('--records', type=int, action='store', help='Number of records per day,  default 10')

        def handle(self, *args, **options):
            from ...models import Client, Product, SimpleSales
            from django.contrib.auth.models import User
            user_id = User.objects.first().pk
            client_count = options.get('clients', 10) or 10
            product_count = options.get('products', 10) or 10
            records_per_day = options.get('records', 10) or 10

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

            # generating sales
            # we will generate 10 records per day for teh whole current year
            sdate = datetime.datetime(datetime.date.today().year, 1, 1)
            edate = datetime.datetime(datetime.date.today().year, 12, 31)

            client_ids = Client.objects.values_list('pk', flat=True)
            product_ids = Product.objects.values_list('pk', flat=True)

            delta = edate - sdate  # as timedelta
            for i in range(delta.days + 1):
                day = sdate + datetime.timedelta(days=i)
                day = pytz.utc.localize(day)
                for z in range(1, records_per_day):
                    SimpleSales.objects.create(
                        doc_date=day,
                        product_id=random.choice(product_ids),
                        client_id=random.choice(client_ids),
                        quantity=random.randrange(1, 10),
                        price=random.randrange(1, 10),
                        lastmod_user_id=user_id
                    )
                self.stdout.write('.', ending='')

            self.stdout.write('')
            self.stdout.write('Done')

Then let's run the command

.. code-block:: console

    $ python manage.py generate_data
    # and here with the default arguments
    $ python manage.py generate_data --clients 10 --products 10 --records 10




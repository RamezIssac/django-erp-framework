Part 1: Create Simple Business Management Application
======================================================

Let's use the project we just generated in the Quickstart section and build an app that manages a business, records and
report its product sales, as well as its expenses, and finally its profitability .

First we need to create an app

.. code-block:: console

    $ django-admin startapp sample_erp

then add `sales` to your ``INSTALLED_APPS``.

Models
------

Below are our models to start building the business management application we want.

.. code-block:: python

    from django.db import models
    from ra.base.models import EntityModel, TransactionModel, TransactionItemModel, QuantitativeTransactionItemModel
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


    class Expense(EntityModel):
        class Meta:
            verbose_name = _('Expense')
            verbose_name_plural = _('Expenses')


    class ExpenseTransaction(TransactionItemModel):
        expense = models.ForeignKey(Expense, on_delete=models.CASCADE)

        class Meta:
            verbose_name = _('Expense Transaction')
            verbose_name_plural = _('Expense Transactions')


    class SalesTransaction(TransactionModel):
        client = models.ForeignKey(Client, on_delete=models.CASCADE)

        class Meta:
            verbose_name = _('Sale')
            verbose_name_plural = _('Sales')


    class SalesLineTransaction(QuantitativeTransactionItemModel):
        product = models.ForeignKey(Product, on_delete=models.CASCADE)
        client = models.ForeignKey(Client, on_delete=models.CASCADE)

        class Meta:
            verbose_name = _('Sale Transaction Line')
            verbose_name_plural = _('Sale Transaction Lines')






The Base Classes we inherit from are fairly straight forward , you can read more about :ref:`base_classes` .
Basically they are there to add common fields in a standard way which will make the orchestration in the system better.

Those fields contains slug field, notes, creator user and creation date, and last modified user and last modified date.
Transactional base model classes include fields like value, price, quantity.

   | **:ref:`entity_model`**: is the Base class from which all other base classes are derived.
   | **QuantitativeTransactionItemModel**: is the base class of a transaction and provide useful fields usually needed for any transaction, like `refer_code`, `doc_date` , `quantity` , `price`, `discount` and `value`


Run ``python manage.py makemigrations sample_erp``, ``python manage.py migrate`` to update the database with your models

The Admin
----------

Ra makes use of the django admin to leverage the process of authentication, authorization and CRUD operation(s).
This is done by

1. Using a different admin site then the default one
2. Using subclassing ModelAdmin which offer many enhancements.

With this information in mind, let's add the below piece of code into `admin.py`

.. code-block:: python

    from .models import Client, Product, Expense, ExpenseTransaction, SalesLineTransaction, SalesTransaction
    from ra.admin.admin import ra_admin_site, EntityAdmin, TransactionAdmin, TransactionItemAdmin


    class ExpenseAdmin(EntityAdmin):
        pass


    class ProductAdmin(EntityAdmin):
        pass


    class ClientAdmin(EntityAdmin):
        pass


    class SalesLineAdmin(TransactionItemAdmin):
        fields = ('product', 'price', 'quantity', 'value')
        model = SalesLineTransaction


    class SalesOrderAdmin(TransactionAdmin):
        inlines = [SalesLineAdmin]
        fields = ['slug', 'doc_date', 'client', ]
        copy_to_formset = ['client']


    ra_admin_site.register(Client, ClientAdmin)
    ra_admin_site.register(Product, ProductAdmin)
    ra_admin_site.register(Expense, ExpenseAdmin)
    ra_admin_site.register(SalesTransaction, SalesOrderAdmin)



Like with models, here we inherit our admin models from ``EntityAdmin``, ``TransactionAdmin``and ``TransactionItemAdmin``
Also we register our model with their AdminModel with ``ra_admin_site`` which is an independent admin site than the default django one.

.. note::

    :ref:`entity_admin` and ``TransactionAdmin`` are just subclasses of `admin.ModelAdmin`. `TransactionItemAdmin` is a subclass of `admin.TabularInline`.
    You can customize it as you'd do normally with any ModelAdmin.
    You can add list_filter(s), select_related, adjust fields and fieldsets on the change_form, etc..

Read more about Admin options: :ref:`ra_admin`

Let's run and access our Dashboard, enter your username and password created with `createsuperuser`.
In the left hand menu you'd find a menu, which will contains links to Clients, Products & SimpleSales admin pages as you'd expect.


Go to the sales order page, add a couple of sale transaction entries.
Now, we notice that

1. *value field* is editable, while it should be readonly
2. The Value field should automatically equals the result of price * quantity.

Front End customization
-----------------------

Let's enhance our Sales Page and make `value` a read only and compute it on the front end and display it to the user.
To do that we need to add a little javascript to handle the client side calculation, and to do that we'll need a create our own template.

Let's customize our admin. Set the add/change form templates and set readonly to the value field widget

.. code-block:: python

    from django import forms

    class SalesOrderAdmin(TransactionAdmin):
        # ...
        add_form_template = change_form_template = 'sample_erp/admin/sales_change_form.html'

        def formfield_for_dbfield(self, db_field, request, **kwargs):
            formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
            if db_field.name == 'value':
                formfield.widget = forms.TextInput(attrs={'readonly': 'readonly'})
            return formfield


Now in you In your `sample_erp` app directory, create a `templates` folder, and inside it you can create
a template file `admin/sales_change_form.html` and in it we can write:

.. code-block:: Django

    {% extends 'ra/change_form.html' %}

    {% block extrajs %}
        {{ block.super }}
        <script>
                django.jQuery(document).ready(function () {
                    const allQuantity = $('[name*=quantity]');
                    const allPrice = $('[name*=price]');

                    function calculateTotal(e) {
                        let holder = $(e.target).parents('.dynamic-saleslinetransaction_set');
                        let $quantity = holder.find('[name*=quantity]');
                        let $price = holder.find('[name*=price]');
                        let quantity = $.ra.smartParseFloat($quantity.val());
                        let price = $.ra.smartParseFloat($price.val());
                        holder.find('[name*=value]').val(quantity * price)
                    }

                    allQuantity.on('change', calculateTotal);
                    allPrice.on('change', calculateTotal);

                    // The newly created rows
                    // ref: https://docs.djangoproject.com/en/2.2/ref/contrib/admin/javascript/
                    django.jQuery(document).on('formset:added', function (event, $row, formsetName) {
                        $row.find('[name*=quantity]').on('change', calculateTotal)
                        $row.find('[name*=price]').on('change', calculateTotal)
                    });
                })
        </script>
    {% endblock %}

Notice here:

1. we `extends` from `ra/change_form.html'`
   This enables us to change themes of your Ra dashboard rather easily. You can read more about :ref:`theming`

2. we use :func:`$.ra.smartParseFloat` in the javascript.
   This is a custom convenience function to handle strings or empty value when numbers are expected (in which case `value` result would be `NaN`.
   If you want to try just replace smartParseFloat with normal `parseFloat` and enter a string or make empty the quantity and/or price field.

   For list of javascript tools available :ref:`javascript`


Now runserver, go to Sales Order and check the outcome, experiment around and add some of sales records, those records will be useful in our next section.
Next Section we will create interesting reports about product sales, which product being bought by which clients and client total sales.

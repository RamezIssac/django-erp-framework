.. _`tutorial_1`:

Sample ERP models and admin
===========================

Let's use the project we just generated in the Quickstart section and build an app that manages a business, records and
report its product sales, as well as its expenses, and finally its profitability .

First we need to create an app

.. code-block:: console

    $ django-admin startapp sample_erp

then add `sample_erp` to your ``INSTALLED_APPS``.

Models
------

To manage a business we would need to track the sales , the clients and the expenses. Here is a sample implementation

.. code-block:: python

    from django.db import models
    from erp_framework.base.models import EntityModel, TransactionModel, TransactionItemModel, QuantitativeTransactionItemModel
    from erp_framework.base.registry import register_doc_type
    from django.utils.translation import gettext_lazy as _


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
        sales_transaction = models.ForeignKey(SalesTransaction, on_delete=models.CASCADE)
        product = models.ForeignKey(Product, on_delete=models.CASCADE)
        client = models.ForeignKey(Client, on_delete=models.CASCADE)

        class Meta:
            verbose_name = _('Sale Transaction Line')
            verbose_name_plural = _('Sale Transaction Lines')






The Base Classes we inherit from are fairly straight forward, basically they encapsulate some typical needed fields and offer related method that serves the system integrity.

Example:

* On ``EntityModel`` those extra fields are `slug`, `notes`, creator user and creation date, and last modified user and last modified date.
* On ``TransactionItemModel`` extra fields are `value` + the above
* On ``QuantitativeTransactionItemModel`` extra fields are `quantity`, `price` and `discount` + all the above

You can read more in :ref:`base_classes`, but for now, that pretty much what we need to know.

Run ``python manage.py makemigrations sample_erp``, ``python manage.py migrate`` to update the database with your models

The Admin
----------

Django ERP framework makes use of the django admin to leverage the process of authentication, authorization and CRUD operation(s).
This is done by

1. Using a different admin site.
2. Using subclasses of ModelAdmin which offer more enhancements.

With this information in mind, let's add the below piece of code into `admin.py`

.. code-block:: python

    from .models import Client, Product, Expense, ExpenseTransaction, SalesLineTransaction, SalesTransaction
    from erp_framework.admin.admin import erp_framework_site, EntityAdmin, TransactionAdmin, TransactionItemAdmin


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


    erp_framework_site.register(Client, ClientAdmin)
    erp_framework_site.register(Product, ProductAdmin)
    erp_framework_site.register(Expense, ExpenseAdmin)
    erp_framework_site.register(SalesTransaction, SalesOrderAdmin)



Like with models, here we inherit our admin models from ``EntityAdmin``, ``TransactionAdmin``and ``TransactionItemAdmin``
Also we register our model with their AdminModel with ``erp_framework_site`` which is an independent admin site than the default django one.

.. note::

    :ref:`entity_admin` and ``TransactionAdmin`` are just subclasses of `admin.ModelAdmin`. `TransactionItemAdmin` is a subclass of `admin.TabularInline`.
    You can customize it as you'd do normally with any ModelAdmin.
    You can add list_filter(s), select_related, adjust fields and fieldsets on the change_form, etc..

Read more about Admin options: :ref:`erp_admin`

Let's run and access our Dashboard, enter your username and password created with `createsuperuser`.
In the left hand menu you'd find a menu, which will contains links to Clients, Products & SimpleSales admin pages as you'd expect.


Go to the sales order page, add a couple of sale transaction entries.
Now, we notice that

1. *value field* is editable, while it should be readonly
2. The Value field should automatically equals the result of price * quantity.


Front End customization
-----------------------

Now we need and compute the value automatically and display it to the user.
To do that we need to add a little javascript to handle the client side calculation, and to do that we'll need a create our own template.


in you In your `sample_erp` app directory, create a `templates` folder, and inside it you can create
a template file `admin/sales_change_form.html` and in it we can write:

.. code-block:: Django

    {% extends 'erp_framework/change_form.html' %}

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
                        let quantity = $.erp_framework.smartParseFloat($quantity.val());
                        let price = $.erp_framework.smartParseFloat($price.val());
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

1. we `extends` from `erp_framework/change_form.html'`
   This enables us to change themes of your Django ERP framework dashboard rather easily. You can read more about :ref:`theming`

2. we use :func:`$.erp_framework.smartParseFloat` in the javascript.
   This is a custom convenience function to handle strings or empty value when numbers are expected (in which case `value` result would be `NaN`.
   If you want to try just replace smartParseFloat with normal `parseFloat` and enter a string or make empty the quantity and/or price field.

   For list of javascript tools available :ref:`javascript`


Now runserver, go to Sales Order and check the outcome, experiment around.


Next Section we will create interesting reports about product sales, which product being bought by which clients and client total sales.

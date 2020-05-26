Create a sales application Part 1
==================================

Let's use the project we just generated in the Quickstart section and build an app that records and track product sales to clients.

First we need to create an app, *you might need to `cd to your project directory first`*

.. code-block:: console

    $ django-admin startapp sales

then add `sales` to your ``INSTALLED_APPS``.

Models
------

To track product sales to clients, we would need 3 models. Client, Product and A Sales Transaction model. Yeah? Let's create them in our `models.py`

.. code-block:: python

    from django.db import models
    from ra.base.models import BaseInfo, BaseMovementInfo, QuanValueMovementItem
    from ra.base.registry import register_doc_type
    from django.utils.translation import ugettext_lazy as _


    class Product(BaseInfo):
        class Meta:
            verbose_name = _('Product')
            verbose_name_plural = _('Products')


    class Client(BaseInfo):
        class Meta:
            verbose_name = _('Client')
            verbose_name_plural = _('Clients')


    class SimpleSales(QuanValueMovementItem):
        client = models.ForeignKey(Client, on_delete=models.CASCADE)
        product = models.ForeignKey(Product, on_delete=models.CASCADE)

        @classmethod
        def get_doc_type(cls):
            return 'sales'

        class Meta:
            verbose_name = _('Sale')
            verbose_name_plural = _('Sales')


    sales = {'name': 'sales', 'plus_list': ['Client'], 'minus_list': ['Product'], }
    register_doc_type(sales)


Two things are worth highlighting here

1. The Base Classes from which we subclassed the Client, Product and SimpleSales models.
   Ra comes with a set a `Base Classes` that orchestrate the system integration, here we used BaseInfo, BasePersonInfo, and QuanValueMovementItem.
   You do not need to worry about them too much now, but for you reference you can read more about :ref:`base_classes`.

   Here is the short version.

   | **BaseInfo**: is the Base class from which all other base classes are derived.
   | **BasePersonInfo** is a subclass of BaseInfo, plus some usual data that would be needed when recording a person data (namely address, telephone, email)
   | **QuanValueMovementItem**: is the base class of a transaction and provide useful fields usually needed for any transaction, like `refer_code`, `doc_date` , `quantity` , `price`, `discount` and `value`


2. The ``doc_type``

   For Ra framework to be able to compute different kind of reports, each transaction need to be recognized and identified how it interacts and affect other models.
   We do so by:

   * setting a *doc_type* to each transaction model we have via the class method `get_doc_type`.
     Ra would throw a `NotImplementedError` if `doc_type` not set on a transaction subclass.

   * Registering the *doc_type* and giving and idea to what it does from an accounting point of view.
     With each sale our products decreases , and client balance (how much they owe our company) increases.



Run ``python manage.py makemigrations sales``, then
``python manage.py migrate`` to update the database with your model

The Admin
----------

Ra makes use of the django admin to leverage the process of authentication, authorization and CRUD operation.

This a great because this gives you an easier learning curve. If you know Django admin you'd easily find your way around RaAdmin
With this information in mind, let's add this piece of code into `admin.py`

.. code-block:: python

    from ra.admin.admin import ra_admin_site, RaAdmin, RaMovementAdmin
    from .models import Client, Product, SimpleSales

    class ClientAdmin(RaAdmin):
        fields = ('slug', 'title', 'notes', 'address', 'email', 'telephone')


    class ProductAdmin(RaAdmin):
        pass


    class SalesOrderAdmin(RaMovementAdmin):
        fields = ['slug', 'doc_date', 'client', ('product', 'price', 'quantity', 'value')]


    ra_admin_site.register(Client, ClientAdmin)
    ra_admin_site.register(Product, ProductAdmin)
    ra_admin_site.register(SimpleSales, SalesOrderAdmin)


This is pretty straight forward. Note that, like with models, here we inherit our admin models from ``RaAdmin`` and ``RaMovementAdmin``.
Also we register our model with their AdminModel with ``ra_admin_site`` which is a totally independent admin site than the "normal" django one.

.. note::

    Keep in mind that RaAdmin and RaMovementAdmin are just subclasses of admin.ModelAdmin. So you can customize it as you'd do normally with any ModelAdmin.

    For example: You can add list_filter, make the foreign key widget to be Select2, adjust which fields and teh fieldsets on the change_form etc.

Read more about :ref:`ra_admin`

Let's run and access our Ra Dashboard, enter your username and password already created with `createsuperuser`.
In the left hand menu you'd find sales menu, which will contains links to Clients, Products & SimpleSales admin pages as you'd expect.


Go to the sales order page, add a couple of sale transaction entries.
Now, we notice that *value field* is editable, while it should be read only, it also should be the result of multiplying price and quantity and this should be done automatically.

.. note::

    `value` is *always* checked and adjusted on server level to as quantity * price (minus any discounts)

.. note::
    In a more real life example, price is automatically recalled from Product Model, this is covered in a later section.

    Also, Sale Order / invoice should be more of an invoice header/footer and invoice details with one-to-many relation. this is also covered later in :ref:`real_world_invoice``
    For now we keep it simple.

Let's enhance our Sales Page and make `value` a read only and compute it on the front end and display it to the user.
To do that we need to add a little javascript to handle the client side calculation, and to do that we'll need a create our own template.

In your `sales` app directory, create a `templates` folder, and inside it you can create
a template file `sales/admin/salesorder_changeform.html` and in it we can write:

.. code-block:: Django

    {% extends RA_THEME|add:'/change_form.html' %}

    {% block admin_change_form_document_ready %}
        <script>
            $(document).ready(function () {
                const $quantity = $('[name*=quantity]');
                const $price = $('[name*=price]');

                function calculateTotal(e) {
                    let quantity = smartParseFloat($quantity.val());
                    let price = smartParseFloat($price.val());
                    $('[name*=value]').val(quantity * price)
                }

                $quantity.on('change', calculateTotal);
                $price.on('change', calculateTotal);
            })
        </script>
    {% endblock %}

Notice here:

1. we `extends` from `RA_THEME|add:'change_form.html'`
   This enables you to change themes of your Ra dashboard rather easily. You can read more about :ref:`theming`


2. we use :func:`smartParseFloat` in the javascript.
   This is a Ra custom javascript tool to handle string or empty value when numbers are expected (in which case `value` result would be `NaN`.
   If you want to try just replace smartParseFloat with normal `parseFloat` and enter a string or make empty the quantity and/or price field.

   For list of javascript tools available :ref:`javascript`

Now we attach this template to our admin model class, and make the value field readonly.

.. code-block:: python

    from django import forms

    class SalesOrderAdmin(RaMovementAdmin):
        ...

        add_form_template = change_form_template = 'sales/admin/salesorder_changeform.html'

        def formfield_for_dbfield(self, db_field, request, **kwargs):
            formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
            if db_field.name == 'value':
                formfield.widget = forms.TextInput(attrs={'readonly': 'readonly'})
            return formfield

Now runserver, go to Sales Order and check the outcome, experiment around and add some of sales records, those records will be useful in our next section.
Next Section we will create interesting reports about product sales, which product being bought by which clients and client total sales.

Carry on !
Tutorial (Part 1) - Simple Sales App
=====================================

Let's use the project we just generated and build a small app that records and track product sales to clients in the project.

Models
------

To track Product sales to clients we would need 3 models, Client, Product and A Sales Transaction model.
Open `ra_demo/models.py` and let's start by adding the code below.


.. code-block:: python

    from django.db import models
    from ra.base.models import BaseInfo, BasePersonInfo, BaseMovementInfo, QuanValueMovementItem
    from ra.base.registry import register_doc_type
    from django.utils.translation import ugettext_lazy as _


    class Product(BaseInfo):
        class Meta:
            verbose_name = _('Product')
            verbose_name_plural = _('Products')


    class Client(BasePersonInfo):
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

Ra comes with a set a :ref:`base_classes` that orchestrate the system integration, here we used BaseInfo, BasePersonInfo, and QuanValueMovementItem

| **BaseInfo**: is the Base class from which all other classes are derived.
| **BasePersonInfo** is a subclass of BaseInfo, plus some usual data that would be needed when recording a person data
  (like address, telephone, email)
| **QuanValueMovementItem**: is the base class of a transaction and provide useful fields
  like `refer_code`, `doc_date` , `quantity` , `price`, `discount` and `value`


For Ra, each transaction need to be recognized.
We do so by:

1. setting a *doc_type* to each transaction model we have via the class method `get_doc_type`.
   Ra would throw a `NotImplementedError` if `doc_type` not set on a transaction subclass.

2. Registering the *doc_type* and giving and idea to what it does from an accounting point of view.
   With each sale our products decreases , and client balance (how much they owe our company) increases.

We will learn more about document types as we go along.

Run ``python manage.py makemigrations ra_demo``, then
``python manage.py migrate`` to update the database with your model

The Admin
----------

Ra makes a great use of the django admin to leverage the process of the data entry / authentication etc.
This a great because this gives you an easier learning curve. If you know Django admin/ you'd easily find your way around Ra.


With this information in mind, let's add this piece of code into `admin.py`

.. code-block:: python

    from ra.admin.admin import ra_admin_site, RaAdmin, RaMovementAdmin
    from .models import Client, Product, SimpleSales

    class ClientAdmin(RaAdmin):
        pass


    class ProductAdmin(RaAdmin):
        pass


    class SalesOrderAdmin(RaMovementAdmin):
        pass


    ra_admin_site.register(Client, ClientAdmin)
    ra_admin_site.register(Product, ProductAdmin)
    ra_admin_site.register(SimpleSales, SalesOrderAdmin)


This is pretty straight forward, Note here that, like with models, here we inherit from a `RaAdmin` and `RaMovementAdmin`.
Also we register our models with their AdminModel with `ra_admin_site` which is a totally independent admin site.


Let's run and access our Ra Dashboard, enter your username and password already created with `createsuperuser`.
In the right hand menu you'd find RA_Demo menu, which will contains links to Clients / Products & SimpleSales admin changelists.


We notice 2 things there:

1. Person does not have the extra fields of the `PersonInfoBase` Class,
2. And in case you didnt notice, Sales only offer Refer Code and date which is not what we want.

Let's add the missing fields to to our RaAdmin classes like how we normally would using django's Admin `fields`

.. code-block:: python

    class ClientAdmin(RaAdmin):
        fields = ('slug', 'title', 'notes', 'address', 'email', 'telephone')


    class SalesOrderAdmin(RaMovementAdmin):
        fields = ['slug', 'doc_date', 'client', ('product', 'price', 'quantity', 'value')]

And let's head to our dashboard and see that indeed we have the new fields for both Client and the Sales Order.


Going to the sales order page, we notice that *value field* is editable, it should be read only.
It also should be the result of multiplying price and quantity and this should be done automatically.

.. note::
    `value` is *always* checked and adjusted on server level to equal quantity * price (minus any discounts)

.. note::
    In a more real life example, price is automatically recalled from Product Model, this is covered in a later section.

    Also, Sale Order / invoice should be more of an invoice header/footer and invoice details with one-to-many relation. this is also covered later.
    For now we keep it simple.

Let's enhance our Sales Page and make value read only and computed on the front end.

First we need to add a little javascript to handle the client side calculation, to do that we'll need a create our own template.
in your `ra_demo` app directory, create a `templates` folder, and inside it you can create
a template file `ra_demo/admin/salesorder_changeform.html`

In this file please type

.. code-block:: javascript

    {% extends 'ra/admin/change_form.html' %}

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

Notice we `extends` from `ra/admin/change_form.html` also notice that we use :func:`smartParseFloat` in the javascript.
This is a Ra custom javascript tool to handle string or empty value (which would result in Value being NaN.
If you want to try just replace smartParseFloat with normal `parseFloat`.

For list of javascript tools available :ref:`javascript`

Now we attach that template to our admin model class

.. code-block:: python

    class SalesOrderAdmin(RaMovementAdmin):
        fields = ['slug', 'doc_date', 'client', ('product', 'price', 'quantity', 'value')]
        add_form_template = change_form_template = 'ra_demo/admin/salesorder_changeform.html'

        def formfield_for_dbfield(self, db_field, request, **kwargs):
            formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
            if db_field.name == 'value':
                formfield.widget = forms.TextInput(attrs={'readonly': 'readonly'})
            return formfield

Now runserver, go to Sales Order and check the outcome, experiment around and add couple of records.

Notice that you have a help button in the up-right corner which walk you through the controls on the page
For more information on customizing help check :ref:`page_help`


You can see also the save buttons have a popup with a short-cut like `Ctrl + a`, this can serves for quicker data entry


Next Section we will create interesting reports about product sales, which product being bought by which clients and client total sales.

Carry on !
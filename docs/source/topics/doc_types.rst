

Document types
===============

What are document types ?
-------------------------

To answer this question we would need to go over a little of accounting and explore the idea of double entry bookkeeping.
Double entry bookkeeping is a system of accounting in which every transaction has a corresponding opposite transaction.
For example, if you buy a car for $10,000, you would record a $10,000 debit to the asset account for your car and a $10,000 credit to the cash account.
Document types are the way to define the type of transaction that is being recorded.

This allows the reporting engine to know how to handle transactions / entries and how to compute it.

Example:

        - A sale is a transaction that will increase the revenue account and decrease the inventory account.
        - A purchase is a transaction that will increase the inventory account and decrease the cash account.
        - A payment is a transaction that will decrease the cash account and decrease the accounts payable account.

The reporting engine will use the document type to know how to compute the transaction.
ie: shall it a plus or a minus, or in accounting terms shall it be a debit or a credit.

The ``ReportView`` have attributes that lets you control the document types .

You can see it in action in the demo application.
In order to compute profitability , the system needed to distinguish between the expenses and the sales
Code on github : https://github.com/RamezIssac/my-shop/blob/main/general_reports/reports.py


.. code-block:: python


        class MyReportView(ReportView):

            doc_type_field_name = "doc_type"
            doc_type_plus_list = ['sales', 'other-revenue']
            doc_type_minus_list = ['expense', 'purchase', 'other-expense']


Here the report will look at the report_model and check the doc_type_field_name (doc_type in the example above)
All the transactions that have a doc_type in the doc_type_plus_list will be added to the plus side of the report calculation
All the transactions that have a doc_type in the doc_type_minus_list will be added to the minus side of the report calculation

This way the report will be able to compute the profit and loss of the company (or any other report that you want to create)


Declaring document type effects
-------------------------------

A transaction class declares how it moves each entity it points to, keyed by the name of the
foreign key. Subclasses inherit the declaration: they can add an entry, override one, or set it to
``None`` (no effect).

.. code-block:: python

        # sales/models.py
        from erp_framework.base.models import EntityModel, TransactionItemModel, TransactionModel
        from erp_framework.doc_types import MINUS, PLUS


        class Customer(EntityModel):
            pass


        class Item(EntityModel):
            pass


        class Treasury(EntityModel):
            pass


        class Sale(TransactionModel):
            customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
            total_quantity = models.DecimalField(max_digits=19, decimal_places=2, default=0)
            discount = models.DecimalField(max_digits=19, decimal_places=2, default=0)
            doc_type_effects = {"customer": PLUS}  # a sale raises what the customer owes


        class SaleItem(TransactionItemModel):  # quantity, price, discount and value per item
            sale = models.ForeignKey(Sale, related_name="items", on_delete=models.CASCADE)
            item = models.ForeignKey(Item, on_delete=models.PROTECT)


        class CashSale(Sale):  # inherits {"customer": PLUS}
            pass


        class CustomerPayment(TransactionModel):
            customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
            treasury = models.ForeignKey(Treasury, on_delete=models.PROTECT)
            # the customer owes less, the treasury holds more
            doc_type_effects = {"customer": MINUS, "treasury": PLUS}

``for_entity(entity, field_name=None)`` returns ``DocTypes(plus, minus)``: the ``get_doc_type()``
values of every installed transaction class that moves ``entity`` through ``field_name`` (default:
the entity's model name). Call it after the models are loaded, for example in a reports module
imported from ``AppConfig.ready()``.

.. code-block:: python

        from erp_framework.doc_types import for_entity

        plus, minus = for_entity(Customer)
        # plus == ["cashsale", "sale"], minus == ["customerpayment"]
        plus, minus = for_entity(Treasury)
        # plus == ["customerpayment"], minus == []

``get_effects(model)`` returns the merged declaration of one class.

System checks:

- ``erp_framework.W001``: a transaction class has a foreign key to an entity and no
  ``doc_type_effects`` entry for it. Declare ``PLUS``, ``MINUS`` or ``None``.
- ``erp_framework.E004``: ``doc_type_effects`` is not a dict, or names a field that is not a foreign key.
- ``erp_framework.E005``: an effect is not ``PLUS``, ``MINUS`` or ``None``.
- ``erp_framework.E006``: one document type is ``PLUS`` for an entity in one class and ``MINUS`` in another.
- ``erp_framework.E007``: a movements column is not numeric on a source that has it, or is a field
  of no source.
- ``erp_framework.E008``: a movements column has different types on two sources (internal type and
  decimal places).
- ``erp_framework.E009``: a ``columns`` mapping names a model that is not a source.
- ``erp_framework.E010``: a declared source has no foreign key to the entity, or two declared
  sources share rows (one inherits from the other).


Movements views
---------------

A report reads one ``report_model``, and doc type lists filter that one table: the customer
payments stored next to the sales are out of their reach. A movements view is a database view that
unions every transaction table with a foreign key to the entity, plus an unmanaged model to query
it.

.. code-block:: python

        entity_movements(Entity, name=None, include_numeric=False, columns=None, exclude=None, sources=None)

- ``name``: the model name, ``<Entity>Movements`` by default. The view belongs to the app that calls
  ``entity_movements()`` and is named ``erp_movements_<app>_<name>``.
- ``sources``: the transaction models to read, one SELECT per model's table. The default is every
  transaction table holding the entity foreign key. A source reaches fields of its MTI parents; list
  a child model to reach the child's own fields.
- ``columns``: fields added by name, as a list (``["discount"]``) or as a dict mapping a column to
  per-source field names. A source is named by its class name or label; a source missing from a
  mapping supplies the field of the column's own name.
- ``include_numeric=True``: every integer, decimal and float field of the sources (primary keys and
  base columns aside), minus the names in ``exclude``.

Every view has the columns ``id`` (text, ``<app>.<model>-<pk>``), ``date``, ``slug``, ``type``,
``value``, ``<entity>_id``, ``content_type_id`` and ``object_id`` of the source row, then the
declared columns. A column takes the type of its first numeric source field and is nullable; a
source without the field gives a typed ``NULL``.

.. code-block:: python

        # sales/models.py, after the transaction classes
        from erp_framework.movements import entity_movements

        # erp_movements_sales_customermovements: Sale (and CashSale) rows plus CustomerPayment rows
        CustomerMovements = entity_movements(Customer, columns=["discount"])  # NULL on payments

        # erp_movements_sales_treasurymovements: the CustomerPayment rows
        TreasuryMovements = entity_movements(Treasury)

Run ``makemigrations``: it records an unmanaged ``CreateModel`` in the app and no SQL.

A project app defines its own movements model next to the library ones. Here a ``custom`` app adds
subscription invoices and a view over sales, subscriptions and payments:

.. code-block:: python

        # custom/models.py
        from erp_framework.base.models import TransactionModel
        from erp_framework.doc_types import PLUS
        from erp_framework.movements import entity_movements
        from sales.models import Customer, CustomerPayment, Sale


        class SubscriptionInvoice(TransactionModel):
            customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
            quantity = models.DecimalField(max_digits=19, decimal_places=2, default=1)  # months billed
            discount = models.DecimalField(max_digits=19, decimal_places=2, default=0)
            doc_type_effects = {"customer": PLUS}


        CustomCustomerMovements = entity_movements(
            Customer,
            name="CustomCustomerMovements",  # view erp_movements_custom_customcustomermovements
            sources=[Sale, SubscriptionInvoice, CustomerPayment],  # these three tables only
            # one "quantity" column from differently named fields, of the same type on each source
            columns={"quantity": {"Sale": "total_quantity", "SubscriptionInvoice": "quantity"}},
            include_numeric=True,  # adds "discount" from Sale and SubscriptionInvoice
            exclude=["total_quantity"],  # already mapped into "quantity"
        )

``CustomCustomerMovements`` has the columns ``quantity`` and ``discount``; the payment rows have
``NULL`` in both.

A report targets a movements model like any model. A report on any movements model of ``Customer``
gets ``base_model = Customer``, unless it sets another entity, and shows in the Customer reports
next to the others:

.. code-block:: python

        # sales/reports.py
        from erp_framework.doc_types import for_entity
        from erp_framework.reporting.registry import register_report_view
        from erp_framework.reporting.views import ReportView


        @register_report_view
        class CustomerBalance(ReportView):
            report_title = "Customer balance"
            report_model = CustomerMovements  # sales and payments in one queryset
            group_by = "customer"
            date_field = "date"
            doc_type_field_name = "type"
            doc_type_plus_list, doc_type_minus_list = for_entity(Customer)  # sales plus, payments minus
            columns = ["name", "__debit__", "__credit__"]  # balance = debit - credit


        # custom/reports.py
        from django.db.models import Sum
        from slick_reporting.fields import ComputationField


        @register_report_view
        class CustomerVolume(ReportView):
            report_title = "Customer volume"
            report_model = CustomCustomerMovements  # listed under Customer, next to CustomerBalance
            group_by = "customer"
            date_field = "date"
            columns = [
                "name",
                ComputationField.create(Sum, "quantity", name="quantity_sum"),  # items sold + months billed
                ComputationField.create(Sum, "discount", name="discount_sum"),
            ]

The SQL is generated from the models and rebuilt by ``migrate``:

- ``pre_migrate`` drops every ``erp_movements_*`` view. Migrations then alter the source tables on
  Postgres and SQLite with movements views present.
- ``post_migrate`` creates the views again from the current models. A source whose table or
  column is not migrated yet (a partial ``migrate <app>``) is left out and reported; the next full
  ``migrate`` adds it.
- ``manage.py rebuild_movement_views`` drops and recreates them; ``--sql`` prints the statements.

A new transaction class needs no report change. A subclass of a declared class inherits its
effect. A new table with a foreign key to the entity joins the movements view at the ``migrate`` that
creates it, and joins the report lists with one ``doc_type_effects`` line.

Note: declare the effect on the new transaction class and not in the report lists, because
``for_entity()`` derives every report's lists from that one declaration.

Movements views support PostgreSQL and SQLite.


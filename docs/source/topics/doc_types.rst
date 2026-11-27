

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

        from erp_framework.doc_types import MINUS, PLUS


        class Movement(TransactionModel):
            customer = models.ForeignKey(Customer, null=True, on_delete=models.PROTECT)
            doc_type_effects = {"customer": None}


        class Sale(Movement):
            doc_type_effects = {"customer": PLUS}


        class SaleReturn(Movement):
            doc_type_effects = {"customer": MINUS}


        class ServiceInvoice(Sale):  # inherits {"customer": PLUS}
            pass


        class CashIn(TreasuryMovement):
            doc_type_effects = {"treasury": PLUS}


        class CustomerPayment(CashIn):  # {"treasury": PLUS, "customer": MINUS}
            customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
            doc_type_effects = {"customer": MINUS}

``for_entity(entity, field_name=None)`` returns ``DocTypes(plus, minus)``: the ``get_doc_type()``
values of every installed transaction class that moves ``entity`` through ``field_name`` (default:
the entity's model name). Call it after the models are loaded, for example in a reports module
imported from ``AppConfig.ready()``.

.. code-block:: python

        from erp_framework.doc_types import for_entity

        plus, minus = for_entity(Customer)
        # plus == ["sale", "serviceinvoice"], minus == ["customerpayment", "salereturn"]

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

A report reads one ``report_model``, and doc type lists filter that one table: a customer payment
stored in the treasury tables is out of their reach. A movements view is a database view that unions every
transaction table with a foreign key to the entity, plus an unmanaged model to query it.

.. code-block:: python

        # models.py of the app that owns the movements model
        from erp_framework.movements import entity_movements

        CustomerMovements = entity_movements(Customer)  # rows grouped by the "customer" foreign key

Run ``makemigrations``: it records an unmanaged ``CreateModel`` and no SQL. The view belongs to the
app that calls ``entity_movements()``: it is named ``erp_movements_<app>_<name>``, where ``name``
defaults to ``<Entity>Movements``. Its columns are ``id`` (text, ``<app>.<model>-<pk>``), ``date``,
``slug``, ``type``, ``value``, ``<entity>_id``, ``content_type_id`` and ``object_id`` of the source
row, then the declared columns.

.. code-block:: python

        entity_movements(Entity, name=None, include_numeric=False, columns=None, exclude=None, sources=None)

- ``include_numeric=True`` adds every integer, decimal and float field of the sources (primary keys
  and the base columns aside), minus the names in ``exclude``.
- ``columns`` adds fields by name, as a list (``["discount"]``) or as a dict mapping a column to
  per-source field names (``{"quantity": {"Sale": "quantity", "MilkSale": "liters"}}``). A source
  is named by its class name or label; a source missing from a mapping supplies the field of the
  column's own name.
- ``sources`` lists the transaction models to read, one SELECT per model's table. The default is
  every transaction table holding the entity foreign key. A source reaches fields of its MTI
  parents; list a child model to reach the child's own fields.
- A column takes the type of its first numeric source field and is nullable. A source without the
  field gives a typed ``NULL``.

Several movements models of one entity live side by side, in the library and in project apps:

.. code-block:: python

        # kheir/models.py
        KheirClientMovements = entity_movements(
            Client,
            name="KheirClientMovements",
            sources=[MilkSale, ClientPayment],
            columns={"liters": {"MilkSale": "liters"}},
        )

A report targets the movements model like any model, with the doc types of the entity. A report on
any movements model of ``Customer`` has ``base_model = Customer``, unless it sets another entity, and
shows in the Customer reports group:

.. code-block:: python

        class CustomerBalance(ReportView):
            report_model = CustomerMovements
            group_by = "customer"
            date_field = "date"
            doc_type_field_name = "type"
            doc_type_plus_list, doc_type_minus_list = for_entity(Customer)
            columns = ["name", "__debit__", "__credit__"]

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


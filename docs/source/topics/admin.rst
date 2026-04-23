.. _erp_admin:

The Admin
#########


Django ERP framework Site
--------------------------
Django ERP framework Site is a custom admin site. It provide you the theme and other goodies aimed to make developement of ERP solutions easier.
It's use is optional.


ModelAdmin Classes
------------------

A subclass of admin.ModelAdmin with various different options


#. `View` page that display all reports about this certain entity / records creating a dashboard out of the box.
#. Comes with settings in place for reversion
#. Usually if a User if given a permission on Model, it means that they have same permissions to its inline models.
   Example: User who can add invoice, is of course permitted to add its *inline* details.
   | This option can be switched off by setting `permission_override_model` on the TransactionInline AdminModel


``EntityAdmin`` offer two important hooks to manage little bit complicated flow

1. it offer `EntityAdmin.pre_save(self, form, formsets, change)`
   It offers you a hook before saving the whole page to do any management you want. Like saving the total of the invoicelines
   in the Invoice.value field.

2. :func:`whole_changeform_validation(self, request, form, formsets, change, **kwargs)`
   Where you'll get a chance to validate the whole page forms and formsets


.. _fk_autocomplete:

FK Autocomplete (Select2 / AJAX)
---------------------------------

All ``EntityAdmin`` subclasses automatically render ForeignKey fields as
Select2 AJAX widgets — no manual ``autocomplete_fields`` declaration needed.

**How it works**

Django's built-in ``autocomplete_fields`` uses Select2 and an AJAX endpoint
that is registered automatically on each admin class. The framework's
``EntityAdmin`` overrides ``get_autocomplete_fields()`` to detect eligible FK
fields at runtime:

- ``EntityAdmin`` already declares ``search_fields = ["name", "slug"]``, so
  every registered entity admin is autocomplete-eligible by default.
- At form render time, each FK field is checked: if the related model's admin
  is registered *and* has ``search_fields``, the field becomes a Select2 widget.

No changes are needed in your own admin classes — it just works.

**Fine-tuning**

1. **Opt a field out** — add its name to ``autocomplete_exclude_fields``:

   .. code-block:: python

       class SalesAdmin(TransactionAdmin):
           autocomplete_exclude_fields = ["agent"]  # agent keeps plain <select>

2. **Full explicit control** — set ``autocomplete_fields`` directly;
   auto-detection is skipped entirely for that admin:

   .. code-block:: python

       class SalesAdmin(TransactionAdmin):
           autocomplete_fields = ["client"]  # only client gets Select2

3. **Customise what is searchable via AJAX** — override ``search_fields`` on
   the *related* model's admin (the default ``["name", "slug"]`` covers most
   cases, but you can extend it):

   .. code-block:: python

       @admin.register(Product)
       class ProductAdmin(EntityAdmin):
           search_fields = ["name", "barcode", "sku"]

   Setting ``search_fields = []`` on a related admin disables autocomplete for
   any FK pointing to that model.

**Inline support**

``TransactionItemAdmin`` (``TabularInline``) applies the same auto-detection,
so inline FK fields (e.g. ``product``, ``store`` on movement lines) also render
as Select2 widgets. The same ``autocomplete_exclude_fields`` attribute and
``autocomplete_fields`` override work on inline classes.

.. _entity_admin:

EntityAdmin
~~~~~~~~~~~
.. autoclass:: erp_framework.admin.admin.EntityAdmin
   :members:


.. _transactionadmin:

TransactionAdmin
~~~~~~~~~~~~~~~~
.. autoclass:: erp_framework.admin.admin.TransactionAdmin
   :members:

.. _transactionitemadmin:

TransactionItemAdmin
~~~~~~~~~~~~~~~~~~~~
.. autoclass:: erp_framework.admin.admin.TransactionItemAdmin
   :members:



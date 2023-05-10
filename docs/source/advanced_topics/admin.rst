.. _erp_admin:

The Admin
#########


Django ERP framework Site
--------------------------
Django ERP framework Site is a custom admin site. It provide you the theme and other goodies aimed to make the dashboard more usable.


ModelAdmin Classes
------------------

A subclass of admin.ModelAdmin with various different options

1. whole_changeform_validation
2. `View` page


``EntityAdmin`` offer two important hooks to manage little bit complicated flow

1. it offer `EntityAdmin.pre_save(self, form, formsets, change)`
   It offers you a hook before saving the whole page to do any management you want. Like saving the total of the invoicelines
   in the Invoice.value field.

2. :func:`whole_changeform_validation(self, request, form, formsets, change, **kwargs)`
   Where you'll get a chance to validate the whole page forms and formsets


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



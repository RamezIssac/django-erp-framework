.. _real_world_invoice:

Real world Invoice Design (Part 5)
==================================

Usually an invoice will formed by at least 2 tables / model where one tale to hold the invoice general data ,
and the other will hold the invoice details.

Let's enhance our SimpleSales by adding a proper invoice model.

in `models.py`

.. code-block:: python

    class Invoice(BaseMovementInfo):
        client = models.ForeignKey(Client, on_delete=models.CASCADE)

        @classmethod
        def get_doc_type(cls):
            return 'sales'


    class InvoiceLine(QuanValueMovementItem):
        invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)

        product = models.ForeignKey(Product, on_delete=models.CASCADE)
        client = models.ForeignKey(Client, on_delete=models.CASCADE)

        @classmethod
        def get_doc_type(cls):
            return 'sales'

.. note::

    we defined `client` *again* in the InvoiceLine. While this may not a good normalization practice,
    this will save a lot of query joining time.

Run `makemigrations` and `migrate`

Then in `admin.py`

.. code-block::  python

    from .models import InvoiceLine, Invoice
    from ra.admin.admin import RaMovementInlineAdmin


    class InvoiceLineAdmin(ra_admin.RaMovementInlineAdmin):
        fields = ['product', 'quantity', 'price', 'discount', 'value']
        model = InvoiceLine


    class InvoiceAdmin(ra_admin.RaMovementAdmin):
        fields = [('slug', 'doc_date'), 'client']
        inlines = [InvoiceLineAdmin]
        copy_to_formset = ['client']


    ra_admin_site.register(Invoice, InvoiceAdmin)



What we did:

1. We Used ``RaMovementInlineAdmin`` which is a subclass of django's `TabularInline` + Ra needed logic and styles.
2. we used the attribute ``copy_to_formset``, which will copy the value of the field (client) from the main form to the formset.

* to do: create front end calculation of line value and total value

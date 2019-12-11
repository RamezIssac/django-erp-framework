Tutorial (Part 5) - Proper Invoice Design
=========================================

Usually an invoice will formed by at least 2 table / models 1 table where
One tale to hold teh invoice general data , and another the invoice details

Let's enhance our SimpleSales by adding a proper invoice model

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

Run `makemigrations` and `migrate`

Then in admnin.py

.. code-block::  python

    class InvoiceLineAdmin(ra_admin.RaMovementInlineAdmin):
        fields = ['product', 'quantity', 'price', 'discount', 'value']
        model = InvoiceLine


    class InvoiceAdmin(ra_admin.RaMovementAdmin):
        fields = [('slug', 'doc_date'), 'client']
        inlines = [InvoiceLineAdmin]
        copy_to_formset = ['client']


    ra_admin_site.register(Invoice, InvoiceAdmin)



Give away:
1. we defined `client` *again* in the InvoiceLine, while this is not normalization but this will save alot of query time.
2. In te admin, we Used ``RaMovementInlineAdmin`` which is like django's `TabularInline`
3. we used the attribute ``copy_to_formset``, to copy the value of the field (client) from the main form to the formset.

* to do create fornt end calculation of line value and total value

``RaAdmin`` offer two important hooks to manage little bit complicated flow

1. it offer :fun:py:`pre_save(self, form, formsets, change)`
   It offers you a hook before saving the whole page to do any management you want. Like saving the total of the invoiceline 
   in the Invoice.value field.
   
2. :func:`whole_changeform_validation(self, request, form, formsets, change, **kwargs)`
   Where you'll get a chance to validate the whole page forms and formsets




* Different doc type sharing same model
* Report views as database views
*
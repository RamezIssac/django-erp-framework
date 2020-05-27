from django.db import models
from django.urls import reverse_lazy

from ra.base.models import TransactionModel, EntityModel, QuantitativeTransactionItemModel, TransactionItemModel
from ra.base.registry import register_doc_type
from django.utils.translation import ugettext_lazy as _


class Product(EntityModel):
    class Meta:
        verbose_name = _('Product')
        verbose_name_plural = _('Products')


class Client(EntityModel):
    criteria = models.CharField(max_length=1, null=True)

    class Meta:
        verbose_name = _('Client')
        verbose_name_plural = _('Clients')


class SimpleSales(QuantitativeTransactionItemModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    @classmethod
    def get_doc_type(cls):
        return 'sales'

    class Meta:
        verbose_name = _('Sale')
        verbose_name_plural = _('Sales')


sales = {'name': 'sales', 'plus_list': ['Client'], 'minus_list': ['Product'],
         'redirect_url_prefix': reverse_lazy('ra_admin:reporting_tests_simplesales_changelist')}

register_doc_type(sales)


class Invoice(TransactionModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)

    @classmethod
    def get_doc_type(cls):
        return 'sales'


class InvoiceLine(QuantitativeTransactionItemModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)

    @classmethod
    def get_doc_type(cls):
        return 'sales'


class Journal(TransactionModel):
    data = models.CharField(max_length=100, null=True, blank=True)

    @classmethod
    def get_doc_type(cls):
        return 'journal-sales'


class JournalItem(TransactionItemModel):
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    data = models.CharField(max_length=100, null=True, blank=True)

    @classmethod
    def get_doc_type(cls):
        return 'journal-sales'


class JournalWithCriteria(Journal):
    class Meta:
        proxy = True


# Vanilla models

class Order(models.Model):
    date_placed = models.DateTimeField(auto_created=True)
    client = models.ForeignKey(Client, null=True, on_delete=models.CASCADE)


class OrderLine(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    client = models.ForeignKey(Client, null=True, on_delete=models.CASCADE)

    # price_before_tax = models.DecimalField()
    # price_after_tax = models.DecimalField()
    # total_value = models.DecimalField()

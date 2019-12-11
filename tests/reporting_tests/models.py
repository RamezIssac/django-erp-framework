
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





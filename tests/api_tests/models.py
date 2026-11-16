from django.db import models

from erp_framework.base.models import (
    EntityModel,
    QuantitativeTransactionItemModel,
    TransactionModel,
)


class Customer(EntityModel):
    pass


class Item(EntityModel):
    pass


class Order(TransactionModel):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)


class OrderLine(QuantitativeTransactionItemModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)

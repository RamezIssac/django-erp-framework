from django.db import models

from erp_framework.base.models import (
    EntityModel,
    QuantitativeTransactionItemModel,
    TransactionModel,
)
from erp_framework.doc_types import MINUS, PLUS


class Customer(EntityModel):
    pass


class Item(EntityModel):
    pass


class Order(TransactionModel):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)

    doc_type_effects = {"customer": PLUS}


class OrderLine(QuantitativeTransactionItemModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)

    doc_type_effects = {"customer": PLUS, "item": MINUS}

from django.db import models

from erp_framework.base.models import (
    EntityModel,
    TransactionItemModel,
    TransactionModel,
)
from erp_framework.doc_types import MINUS, PLUS
from erp_framework.movements import entity_movements


class Customer(EntityModel):
    pass


class Treasury(EntityModel):
    pass


class Movement(TransactionModel):
    slug = models.SlugField(max_length=60, blank=True, db_index=True)
    customer = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.CASCADE
    )
    discount = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    quantity = models.IntegerField(default=0)

    doc_type_effects = {"customer": None}


class Sale(Movement):
    doc_type_effects = {"customer": PLUS}


class SaleReturn(Movement):
    returned_units = models.IntegerField(default=0)

    doc_type_effects = {"customer": MINUS}


class ServiceInvoice(Sale):
    pass


class SaleLine(TransactionItemModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE)


class TreasuryMovement(TransactionModel):
    treasury = models.ForeignKey(Treasury, on_delete=models.CASCADE)
    discount = models.DecimalField(max_digits=19, decimal_places=2, default=0)

    doc_type_effects = {"treasury": None}


class CashIn(TreasuryMovement):
    doc_type_effects = {"treasury": PLUS}


class CashOut(TreasuryMovement):
    doc_type_effects = {"treasury": MINUS}

    @classmethod
    def get_doc_type(cls):
        return "cash-out"


class CustomerPayment(CashIn):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

    doc_type_effects = {"customer": MINUS}


CustomerMovements = entity_movements(Customer, include_numeric=True)
TreasuryMovements = entity_movements(Treasury)

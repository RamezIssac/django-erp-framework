from movements_tests.models import Customer, Sale, SaleReturn

from erp_framework.movements import entity_movements

CustomerSales = entity_movements(
    Customer,
    name="CustomerSales",
    sources=[Sale, SaleReturn],
    columns={"units": {"Sale": "quantity", "SaleReturn": "returned_units"}, "discount": {}},
)

from unittest import mock

from django.test import SimpleTestCase

from erp_framework.doc_types import (
    MINUS,
    PLUS,
    DocTypes,
    check_doc_type_effects,
    for_entity,
    get_effects,
    transaction_models,
)

from .models import (
    CashIn,
    CashOut,
    Customer,
    CustomerPayment,
    Movement,
    Sale,
    SaleLine,
    SaleReturn,
    ServiceInvoice,
    Treasury,
)


def check_ids(models=None):
    return [
        error.id for error in check_doc_type_effects(models or transaction_models())
    ]


class ForEntityTests(SimpleTestCase):
    def test_customer_types_span_two_tables(self):
        self.assertEqual(
            for_entity(Customer),
            DocTypes(
                plus=["sale", "serviceinvoice"], minus=["customerpayment", "salereturn"]
            ),
        )

    def test_treasury_types_include_the_payment_subclass(self):
        self.assertEqual(
            for_entity(Treasury, "treasury"),
            DocTypes(plus=["cashin", "customerpayment"], minus=["cash-out"]),
        )

    def test_neutral_effect_is_left_out(self):
        self.assertNotIn(
            "movement", for_entity(Customer).plus + for_entity(Customer).minus
        )

    def test_foreign_key_to_another_model_is_ignored(self):
        self.assertEqual(for_entity(Customer, "treasury"), DocTypes([], []))

    def test_new_type_needs_one_line(self):
        with mock.patch.object(Movement, "doc_type_effects", {"customer": PLUS}):
            self.assertIn("movement", for_entity(Customer).plus)


class DocTypeRegistryBugTests(SimpleTestCase):
    """The four ways the previous registry failed, each checked against its replacement."""

    def test_declaring_an_effect_needs_no_registration_call(self):
        # Before: registering a DocType instance raised ImproperlyConfigured.
        self.assertEqual(get_effects(Sale), {"customer": PLUS})
        self.assertEqual(get_effects(ServiceInvoice), {"customer": PLUS})

    def test_misspelled_declaration_is_reported(self):
        # Before: plus_side/plus_list key mismatch registered an empty map without a word.
        with mock.patch.object(Sale, "doc_type_effects", {"custmer": PLUS}):
            self.assertIn("erp_framework.E004", check_ids([Sale]))
        with mock.patch.object(Sale, "doc_type_effects", {"customer": "plus"}):
            self.assertIn("erp_framework.E005", check_ids([Sale]))
        with mock.patch.object(Sale, "doc_type_effects", {"customer": True}):
            self.assertIn("erp_framework.E005", check_ids([Sale]))

    def test_declaring_class_keeps_its_own_doc_type(self):
        # Before: @doc_type_registry.register returned None and replaced the decorated class.
        self.assertEqual(CashOut.get_doc_type(), "cash-out")
        self.assertEqual(for_entity(Treasury).minus, ["cash-out"])

    def test_inheritance_adds_overrides_and_removes_without_mutating_bases(self):
        # Before: set/append/remove unpacked the stored dict and raised or corrupted it.
        self.assertEqual(
            get_effects(CustomerPayment), {"treasury": PLUS, "customer": MINUS}
        )
        self.assertEqual(CashIn.doc_type_effects, {"treasury": PLUS})
        self.assertEqual(get_effects(SaleReturn), {"customer": MINUS})
        self.assertEqual(Movement.doc_type_effects, {"customer": None})
        with mock.patch.object(CustomerPayment, "doc_type_effects", {"treasury": None}):
            self.assertEqual(get_effects(CustomerPayment), {"treasury": None})
            self.assertNotIn("customerpayment", for_entity(Treasury).plus)


class DocTypeChecksTests(SimpleTestCase):
    def test_project_models_pass(self):
        self.assertEqual(check_doc_type_effects(transaction_models()), [])

    def test_missing_effect_warns(self):
        with mock.patch.object(Movement, "doc_type_effects", {}):
            errors = check_doc_type_effects([Movement])
        self.assertEqual([e.id for e in errors], ["erp_framework.W001"])
        self.assertIn("'customer'", errors[0].msg)

    def test_foreign_key_to_a_transaction_is_not_an_entity(self):
        self.assertEqual(SaleLine.__dict__.get("doc_type_effects"), None)
        self.assertEqual(check_ids([SaleLine]), [])

    def test_same_type_with_opposite_signs_is_an_error(self):
        with mock.patch.object(
            SaleReturn, "get_doc_type", classmethod(lambda cls: "sale")
        ):
            self.assertIn("erp_framework.E006", check_ids([Sale, SaleReturn]))

    def test_not_a_dict_is_an_error(self):
        with mock.patch.object(Sale, "doc_type_effects", ["customer"]):
            self.assertEqual(check_ids([Sale]), ["erp_framework.E004"])

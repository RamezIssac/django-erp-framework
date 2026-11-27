from unittest import mock

from django.apps import apps
from django.core import checks
from django.test import SimpleTestCase
from django.test.utils import isolate_apps

from erp_framework.doc_types import (
    MINUS,
    PLUS,
    DocTypes,
    check_doc_type_effects,
    entity_foreign_key,
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


def proxy_of(model, **attrs):
    meta = type("Meta", (), {"proxy": True, "app_label": "movements_tests"})
    return type(f"{model.__name__}Proxy", (model,), {"__module__": __name__, "Meta": meta, **attrs})


class DocTypeMessagesTests(SimpleTestCase):
    def test_declaration_errors_name_the_field_and_the_fix(self):
        with mock.patch.object(Sale, "doc_type_effects", {"custmer": PLUS, "customer": 2}):
            bad_effect, not_fk = check_doc_type_effects([Sale])
        self.assertEqual(not_fk.msg, "doc_type_effects names 'custmer', which is not a foreign key of movements_tests.Sale.")
        self.assertEqual(not_fk.hint, "Use the name of a ForeignKey field of the model.")
        self.assertEqual(bad_effect.msg, "doc_type_effects['customer'] of movements_tests.Sale is 2.")
        self.assertEqual(bad_effect.hint, "Use PLUS, MINUS or None from erp_framework.doc_types.")
        with mock.patch.object(Sale, "doc_type_effects", ["customer"]), mock.patch.object(Movement, "doc_type_effects", {}):
            not_a_dict, missing = check_doc_type_effects([Sale, Movement])
        self.assertEqual(not_a_dict.msg, "doc_type_effects of movements_tests.Sale is not a dict.")
        self.assertEqual(missing.id, "erp_framework.W001")

    def test_missing_effect_message_and_hint(self):
        with mock.patch.object(Movement, "doc_type_effects", {}):
            (warning,) = check_doc_type_effects([Movement])
        self.assertEqual(
            warning.msg, "movements_tests.Movement has a foreign key 'customer' to movements_tests.Customer and no doc_type_effects entry for it."
        )
        self.assertEqual(
            warning.hint,
            "Declare doc_type_effects = {'customer': PLUS} (or MINUS, or None for no effect) on the class or one of its bases.",
        )

    def test_opposite_signs_message_lists_the_classes(self):
        with mock.patch.object(SaleReturn, "get_doc_type", classmethod(lambda cls: "sale")):
            (error,) = check_doc_type_effects([Sale, SaleReturn])
        self.assertEqual(
            error.msg,
            "Document type 'sale' is both PLUS and MINUS for movements_tests.Customer through 'customer' "
            "(movements_tests.Sale, movements_tests.SaleReturn).",
        )
        self.assertEqual(error.hint, "Give the classes distinct get_doc_type() values or the same effect.")

    def test_doc_types_repr(self):
        self.assertEqual(repr(DocTypes(["sale"], [])), "DocTypes(plus=['sale'], minus=[])")


class DocTypeModelsTests(SimpleTestCase):
    def test_reverse_relation_is_not_a_foreign_key(self):
        self.assertIsNone(entity_foreign_key(Customer, "movement", Movement))

    @isolate_apps("movements_tests")
    def test_proxies_count_for_entities_and_inherited_checks_are_not_repeated(self):
        declared = proxy_of(SaleReturn, doc_type_effects={"customer": PLUS})
        inherited = proxy_of(Sale)
        with mock.patch.object(apps, "get_models", lambda: [Movement, Sale, declared, inherited]):
            self.assertIn(declared.get_doc_type(), for_entity(Customer).plus)
        with mock.patch.object(declared, "doc_type_effects", {"custmer": PLUS}):
            self.assertEqual(check_ids([inherited, declared]), ["erp_framework.E004"])
        with mock.patch.object(Movement, "doc_type_effects", {}), mock.patch.object(Sale, "doc_type_effects", {}):
            self.assertEqual(check_ids([inherited, ServiceInvoice]), ["erp_framework.W001"])

    def test_check_is_registered_and_follows_app_configs(self):
        from erp_framework.checks import doc_type_effects_check

        self.assertIn(doc_type_effects_check, checks.registry.registry.get_checks())
        with mock.patch.object(Movement, "doc_type_effects", {}):
            ids = [e.id for e in doc_type_effects_check([apps.get_app_config("movements_tests")])]
            self.assertEqual(ids, ["erp_framework.W001"])
            self.assertEqual(doc_type_effects_check([apps.get_app_config("auth")]), [])

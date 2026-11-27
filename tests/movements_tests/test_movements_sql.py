from dataclasses import replace
from importlib import import_module
from types import SimpleNamespace
from unittest import mock

from django.apps import apps
from django.test import SimpleTestCase
from django.test.utils import isolate_apps

from erp_framework.checks import movements_check
from erp_framework.movements import (
    MovementsModel,
    _quote,
    _source_select,
    _sql_str,
    build_movements_sql,
    check_movements,
    entity_movements,
    movement_columns,
    movement_sources,
)

from .models import (
    Customer,
    CustomerMovements,
    CustomerPayment,
    Movement,
    Sale,
    TreasuryMovement,
    TreasuryMovements,
)

# include_numeric: discount on both tables (the payment's from its MTI parent), quantity on movements only.
CUSTOMER_MOVEMENTS_SQL = """\
CREATE VIEW "erp_movements_movements_tests_customermovements" AS
SELECT 'movements_tests.customerpayment-' || CAST(s0."cashin_ptr_id" AS TEXT) AS "id",
       s0p1."date" AS "date",
       s0p1."slug" AS "slug",
       s0p1."type" AS "type",
       s0p1."value" AS "value",
       (SELECT "id" FROM "django_content_type" WHERE "app_label" = 'movements_tests' AND "model" = 'customerpayment') AS "content_type_id",
       CAST(s0."cashin_ptr_id" AS TEXT) AS "object_id",
       s0."customer_id" AS "customer_id",
       s0p1."discount" AS "discount",
       CAST(NULL AS integer) AS "quantity"
FROM "movements_tests_customerpayment" s0
JOIN "movements_tests_treasurymovement" s0p1 ON s0p1."id" = s0."cashin_ptr_id"
WHERE s0."customer_id" IS NOT NULL
UNION ALL
SELECT 'movements_tests.movement-' || CAST(s1."id" AS TEXT) AS "id",
       s1."date" AS "date",
       s1."slug" AS "slug",
       s1."type" AS "type",
       s1."value" AS "value",
       (SELECT "id" FROM "django_content_type" WHERE "app_label" = 'movements_tests' AND "model" = 'movement') AS "content_type_id",
       CAST(s1."id" AS TEXT) AS "object_id",
       s1."customer_id" AS "customer_id",
       s1."discount" AS "discount",
       s1."quantity" AS "quantity"
FROM "movements_tests_movement" s1
WHERE s1."customer_id" IS NOT NULL"""

CUSTOMER_DISCOUNTS_SQL = """\
CREATE VIEW "erp_movements_movements_tests_customerdiscounts" AS
SELECT 'movements_tests.customerpayment-' || CAST(s0."cashin_ptr_id" AS TEXT) AS "id",
       s0p1."date" AS "date",
       s0p1."slug" AS "slug",
       s0p1."type" AS "type",
       s0p1."value" AS "value",
       (SELECT "id" FROM "django_content_type" WHERE "app_label" = 'movements_tests' AND "model" = 'customerpayment') AS "content_type_id",
       CAST(s0."cashin_ptr_id" AS TEXT) AS "object_id",
       s0."customer_id" AS "customer_id",
       s0p1."discount" AS "discount"
FROM "movements_tests_customerpayment" s0
JOIN "movements_tests_treasurymovement" s0p1 ON s0p1."id" = s0."cashin_ptr_id"
WHERE s0."customer_id" IS NOT NULL
UNION ALL
SELECT 'movements_tests.movement-' || CAST(s1."id" AS TEXT) AS "id",
       s1."date" AS "date",
       s1."slug" AS "slug",
       s1."type" AS "type",
       s1."value" AS "value",
       (SELECT "id" FROM "django_content_type" WHERE "app_label" = 'movements_tests' AND "model" = 'movement') AS "content_type_id",
       CAST(s1."id" AS TEXT) AS "object_id",
       s1."customer_id" AS "customer_id",
       s1."discount" AS "discount"
FROM "movements_tests_movement" s1
WHERE s1."customer_id" IS NOT NULL"""

TREASURY_MOVEMENTS_SQL = """\
CREATE VIEW "erp_movements_movements_tests_treasurymovements" AS
SELECT 'movements_tests.treasurymovement-' || CAST(s0."id" AS TEXT) AS "id",
       s0."date" AS "date",
       s0."slug" AS "slug",
       s0."type" AS "type",
       s0."value" AS "value",
       (SELECT "id" FROM "django_content_type" WHERE "app_label" = 'movements_tests' AND "model" = 'treasurymovement') AS "content_type_id",
       CAST(s0."id" AS TEXT) AS "object_id",
       s0."treasury_id" AS "treasury_id"
FROM "movements_tests_treasurymovement" s0
WHERE s0."treasury_id" IS NOT NULL"""

EMPTY_CUSTOMER_MOVEMENTS_SQL = {
    "postgresql": """\
CREATE VIEW "erp_movements_movements_tests_customermovements" AS
SELECT CAST(NULL AS text) AS "id",
       CAST(NULL AS timestamp with time zone) AS "date",
       CAST(NULL AS varchar(50)) AS "slug",
       CAST(NULL AS varchar(30)) AS "type",
       CAST(NULL AS numeric(19, 2)) AS "value",
       CAST(NULL AS integer) AS "content_type_id",
       CAST(NULL AS text) AS "object_id",
       CAST(NULL AS bigint) AS "customer_id",
       CAST(NULL AS numeric(19, 2)) AS "discount",
       CAST(NULL AS integer) AS "quantity"
WHERE 1 = 0""",
    "sqlite": """\
CREATE VIEW "erp_movements_movements_tests_customermovements" AS
SELECT NULL AS "id",
       NULL AS "date",
       NULL AS "slug",
       NULL AS "type",
       NULL AS "value",
       NULL AS "content_type_id",
       NULL AS "object_id",
       NULL AS "customer_id",
       NULL AS "discount",
       NULL AS "quantity"
WHERE 1 = 0""",
}

BACKENDS = ("postgresql", "sqlite3")


def backend_connection(backend):
    return import_module(f"django.db.backends.{backend}.base").DatabaseWrapper({})


class MovementsSqlGoldenTests(SimpleTestCase):
    def test_include_numeric(self):
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                sql = build_movements_sql(CustomerMovements, backend_connection(backend))
                self.assertEqual(sql, CUSTOMER_MOVEMENTS_SQL)

    @isolate_apps("movements_tests")
    def test_include_numeric_with_exclude(self):
        model = entity_movements(Customer, name="CustomerDiscounts", include_numeric=True, exclude=["quantity"])
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                self.assertEqual(build_movements_sql(model, backend_connection(backend)), CUSTOMER_DISCOUNTS_SQL)

    def test_without_columns(self):
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                sql = build_movements_sql(TreasuryMovements, backend_connection(backend))
                self.assertEqual(sql, TREASURY_MOVEMENTS_SQL)

    def test_postgresql_without_sources_has_typed_columns(self):
        self.assertEqual(
            build_movements_sql(CustomerMovements, backend_connection("postgresql"), []),
            EMPTY_CUSTOMER_MOVEMENTS_SQL["postgresql"],
        )

    def test_sqlite_without_sources(self):
        self.assertEqual(
            build_movements_sql(CustomerMovements, backend_connection("sqlite3"), []),
            EMPTY_CUSTOMER_MOVEMENTS_SQL["sqlite"],
        )

    def test_unsupported_vendor(self):
        with self.assertRaises(NotImplementedError) as raised:
            build_movements_sql(CustomerMovements, SimpleNamespace(vendor="mysql"))
        self.assertEqual(str(raised.exception), "Movements views support postgresql, sqlite, not mysql.")

    def test_names_and_strings_are_escaped(self):
        self.assertEqual(_quote('odd"name'), '"odd""name"')
        self.assertEqual(_sql_str("o'clock"), "'o''clock'")

    def test_polymorphic_ctype_column_replaces_the_content_type_lookup(self):
        get_field = Movement._meta.get_field

        def with_ctype(name):
            return get_field("customer" if name == "polymorphic_ctype" else name)

        with mock.patch.object(Movement._meta, "get_field", with_ctype):
            sql = _source_select(CustomerMovements, Movement, 0, backend_connection("sqlite3"))[0]
        self.assertIn('s0."customer_id" AS "content_type_id"', sql)
        self.assertNotIn("django_content_type", sql)


class MovementsModelTests(SimpleTestCase):
    def test_one_source_per_table(self):
        self.assertEqual(movement_sources(CustomerMovements), [CustomerPayment, Movement])
        self.assertEqual(movement_sources(TreasuryMovements), [TreasuryMovement])

    def test_factory_output(self):
        meta = CustomerMovements._meta
        self.assertTrue(issubclass(CustomerMovements, MovementsModel))
        self.assertFalse(meta.managed)
        self.assertEqual(meta.app_label, "movements_tests")
        self.assertEqual(meta.db_table, "erp_movements_movements_tests_customermovements")
        self.assertIs(meta.get_field("customer").related_model, Customer)
        self.assertEqual(CustomerMovements.movements_field, "customer")
        labels = {name: str(meta.get_field(name).verbose_name) for name in ("date", "slug", "type", "value")}
        self.assertEqual(labels, {"date": "Date", "slug": "Slug", "type": "Type", "value": "Value"})

    def test_columns_copy_the_type_of_their_first_source_field(self):
        meta = CustomerMovements._meta
        self.assertEqual(list(movement_columns(CustomerMovements)), ["discount", "quantity"])
        self.assertEqual([f.name for f in meta.concrete_fields][-3:], ["customer", "discount", "quantity"])
        discount, quantity = meta.get_field("discount"), meta.get_field("quantity")
        self.assertEqual((type(discount).__name__, discount.decimal_places, discount.null), ("DecimalField", 2, True))
        self.assertEqual((type(quantity).__name__, quantity.null), ("IntegerField", True))

    def test_column_names_must_not_be_base_columns(self):
        for columns in (["value"], ["customer_id"], {"date": {}}):
            with self.subTest(columns=columns), self.assertRaises(ValueError):
                entity_movements(Customer, columns=columns)

    @isolate_apps("movements_tests")
    def test_checks(self):
        cases = [
            (
                {"columns": ["quantity", "notes", "missing"]},
                [
                    ("E007", "Column 'notes' of {label} is not numeric on "
                     "movements_tests.CustomerPayment, movements_tests.Movement."),
                    ("E007", "Column 'missing' of {label} is not a field of any source."),
                ],
            ),
            (
                {"columns": {"units": {"Movement": "quantity", "CustomerPayment": "discount"}}},
                [("E008", "Column 'units' of {label} is DecimalField(2 places) on "
                  "movements_tests.CustomerPayment and IntegerField on movements_tests.Movement.")],
            ),
            (
                {"columns": {"units": {"Movement": "quantity", "Bogus": "quantity"}}},
                [("E009", "Column 'units' of {label} maps 'Bogus', which is not a source.")],
            ),
            (
                {"sources": [TreasuryMovement]},
                [("E010", "Source movements_tests.TreasuryMovement of {label} has no foreign key "
                  "'customer' to movements_tests.Customer.")],
            ),
            (
                {"sources": [Movement, Sale]},
                [("E010", "Sources movements_tests.Movement and movements_tests.Sale of {label} "
                  "share rows: list one of them.")],
            ),
        ]
        for number, (kwargs, expected) in enumerate(cases):
            with self.subTest(kwargs=kwargs):
                model = entity_movements(Customer, name=f"M{number}", **kwargs)
                found = [(e.id.split(".")[1], e.msg) for e in check_movements([model])]
                label = model._meta.label
                self.assertEqual(found, [(id, msg.replace("{label}", label)) for id, msg in expected])

    def test_check_is_registered_and_follows_app_configs(self):
        spec = replace(CustomerMovements.movements_spec, columns={"discount": {"Bogus": "discount"}})
        with mock.patch.object(CustomerMovements, "movements_spec", spec):
            self.assertEqual(
                [e.id for e in movements_check([apps.get_app_config("movements_tests")])],
                ["erp_framework.E009"],
            )
            self.assertEqual(movements_check([apps.get_app_config("auth")]), [])

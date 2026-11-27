from importlib import import_module
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from django.test.utils import isolate_apps

from erp_framework.checks import movements_extra_columns_check
from erp_framework.movements import (
    MovementsModel,
    _quote,
    _source_select,
    _sql_str,
    build_movements_sql,
    check_extra_columns,
    entity_movements,
    movement_sources,
)

from .models import (
    Customer,
    CustomerMovements,
    CustomerPayment,
    Movement,
    TreasuryMovements,
    TreasuryMovement,
)

CUSTOMER_MOVEMENTS_SQL = """\
CREATE VIEW "erp_movements_movements_tests_customer" AS
SELECT 'movements_tests.customerpayment-' || CAST(s0."cashin_ptr_id" AS TEXT) AS "id",
       s0p1."date" AS "date",
       s0p1."slug" AS "slug",
       s0p1."type" AS "type",
       s0p1."value" AS "value",
       (SELECT "id" FROM "django_content_type" WHERE "app_label" = 'movements_tests' AND "model" = 'customerpayment') AS "content_type_id",
       CAST(s0."cashin_ptr_id" AS TEXT) AS "object_id",
       s0."customer_id" AS "customer_id",
       CAST(s0p1."discount" AS {numeric}) AS "discount",
       CAST(0 AS {numeric}) AS "quantity"
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
       CAST(s1."discount" AS {numeric}) AS "discount",
       CAST(s1."quantity" AS {numeric}) AS "quantity"
FROM "movements_tests_movement" s1
WHERE s1."customer_id" IS NOT NULL"""
NUMERIC = {"postgresql": "numeric(19, 2)", "sqlite3": "decimal"}

TREASURY_MOVEMENTS_SQL = """\
CREATE VIEW "erp_movements_movements_tests_treasury" AS
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
CREATE VIEW "erp_movements_movements_tests_customer" AS
SELECT CAST(NULL AS text) AS "id",
       CAST(NULL AS timestamp with time zone) AS "date",
       CAST(NULL AS varchar(50)) AS "slug",
       CAST(NULL AS varchar(30)) AS "type",
       CAST(NULL AS numeric(19, 2)) AS "value",
       CAST(NULL AS integer) AS "content_type_id",
       CAST(NULL AS text) AS "object_id",
       CAST(NULL AS bigint) AS "customer_id",
       CAST(NULL AS numeric(19, 2)) AS "discount",
       CAST(NULL AS numeric(19, 2)) AS "quantity"
WHERE 1 = 0""",
    "sqlite": """\
CREATE VIEW "erp_movements_movements_tests_customer" AS
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


def backend_connection(backend):
    return import_module(f"django.db.backends.{backend}.base").DatabaseWrapper({})


class MovementsSqlGoldenTests(SimpleTestCase):
    def test_extra_columns_come_from_each_source_or_a_typed_zero(self):
        for backend in ("postgresql", "sqlite3"):
            with self.subTest(backend=backend):
                self.assertEqual(
                    build_movements_sql(CustomerMovements, backend_connection(backend)),
                    CUSTOMER_MOVEMENTS_SQL.format(numeric=NUMERIC[backend]),
                )

    def test_without_extra_columns(self):
        for backend in ("postgresql", "sqlite3"):
            with self.subTest(backend=backend):
                self.assertEqual(
                    build_movements_sql(TreasuryMovements, backend_connection(backend)),
                    TREASURY_MOVEMENTS_SQL,
                )

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
        self.assertEqual(meta.db_table, "erp_movements_movements_tests_customer")
        self.assertIs(meta.get_field("customer").related_model, Customer)
        self.assertEqual(CustomerMovements.movements_field, "customer")
        labels = {name: str(meta.get_field(name).verbose_name) for name in ("date", "slug", "type", "value")}
        self.assertEqual(labels, {"date": "Date", "slug": "Slug", "type": "Type", "value": "Value"})
        extras = {name: type(meta.get_field(name)).__name__ for name in CustomerMovements.movements_extra_columns}
        self.assertEqual(extras, {"discount": "DecimalField", "quantity": "DecimalField"})

    def test_extra_column_names_must_be_new_and_distinct(self):
        for extra_columns in (["value"], ["customer_id"], ["discount", "discount"]):
            with self.subTest(extra_columns=extra_columns), self.assertRaises(ValueError):
                entity_movements(Customer, extra_columns=extra_columns)

    @isolate_apps("movements_tests")
    def test_extra_columns_check(self):
        model = entity_movements(Customer, extra_columns=["quantity", "notes", "missing"])
        self.assertEqual(
            [(e.id, e.msg) for e in check_extra_columns([model])],
            [
                (
                    "erp_framework.E007",
                    "Extra column 'notes' of movements_tests.CustomerMovements is not numeric on "
                    "movements_tests.CustomerPayment, movements_tests.Movement.",
                ),
                (
                    "erp_framework.E007",
                    "Extra column 'missing' of movements_tests.CustomerMovements is not a field of any source.",
                ),
            ],
        )

    def test_extra_columns_check_is_registered_and_follows_app_configs(self):
        from django.apps import apps

        with mock.patch.object(CustomerMovements, "movements_extra_columns", ("missing",)):
            self.assertEqual(
                [e.id for e in movements_extra_columns_check([apps.get_app_config("movements_tests")])],
                ["erp_framework.E007"],
            )
            self.assertEqual(movements_extra_columns_check([apps.get_app_config("auth")]), [])

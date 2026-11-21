from django.test import SimpleTestCase

from erp_framework.ledgers import LedgerModel, build_ledger_sql, ledger_sources

from .models import (
    Customer,
    CustomerLedger,
    CustomerPayment,
    Movement,
    TreasuryLedger,
    TreasuryMovement,
)

CUSTOMER_LEDGER_SQL = """\
CREATE VIEW "erp_ledger_ledger_tests_customer" AS
SELECT 'ledger_tests.customerpayment-' || CAST(s0."cashin_ptr_id" AS TEXT) AS "id",
       s0p1."date" AS "date",
       s0p1."slug" AS "slug",
       s0p1."type" AS "type",
       s0p1."value" AS "value",
       (SELECT "id" FROM "django_content_type" WHERE "app_label" = 'ledger_tests' AND "model" = 'customerpayment') AS "content_type_id",
       CAST(s0."cashin_ptr_id" AS TEXT) AS "object_id",
       s0."customer_id" AS "customer_id"
FROM "ledger_tests_customerpayment" s0
JOIN "ledger_tests_treasurymovement" s0p1 ON s0p1."id" = s0."cashin_ptr_id"
WHERE s0."customer_id" IS NOT NULL
UNION ALL
SELECT 'ledger_tests.movement-' || CAST(s1."id" AS TEXT) AS "id",
       s1."date" AS "date",
       s1."slug" AS "slug",
       s1."type" AS "type",
       s1."value" AS "value",
       (SELECT "id" FROM "django_content_type" WHERE "app_label" = 'ledger_tests' AND "model" = 'movement') AS "content_type_id",
       CAST(s1."id" AS TEXT) AS "object_id",
       s1."customer_id" AS "customer_id"
FROM "ledger_tests_movement" s1
WHERE s1."customer_id" IS NOT NULL"""

EMPTY_CUSTOMER_LEDGER_SQL = {
    "postgresql": """\
CREATE VIEW "erp_ledger_ledger_tests_customer" AS
SELECT CAST(NULL AS text) AS "id",
       CAST(NULL AS timestamp with time zone) AS "date",
       CAST(NULL AS varchar(50)) AS "slug",
       CAST(NULL AS varchar(30)) AS "type",
       CAST(NULL AS numeric(19, 2)) AS "value",
       CAST(NULL AS integer) AS "content_type_id",
       CAST(NULL AS text) AS "object_id",
       CAST(NULL AS bigint) AS "customer_id"
WHERE 1 = 0""",
    "sqlite": """\
CREATE VIEW "erp_ledger_ledger_tests_customer" AS
SELECT NULL AS "id",
       NULL AS "date",
       NULL AS "slug",
       NULL AS "type",
       NULL AS "value",
       NULL AS "content_type_id",
       NULL AS "object_id",
       NULL AS "customer_id"
WHERE 1 = 0""",
}


class LedgerSqlGoldenTests(SimpleTestCase):
    def test_postgresql(self):
        self.assertEqual(
            build_ledger_sql(CustomerLedger, "postgresql"), CUSTOMER_LEDGER_SQL
        )

    def test_sqlite(self):
        self.assertEqual(
            build_ledger_sql(CustomerLedger, "sqlite"), CUSTOMER_LEDGER_SQL
        )

    def test_postgresql_without_sources_has_typed_columns(self):
        self.assertEqual(
            build_ledger_sql(CustomerLedger, "postgresql", []),
            EMPTY_CUSTOMER_LEDGER_SQL["postgresql"],
        )

    def test_sqlite_without_sources(self):
        self.assertEqual(
            build_ledger_sql(CustomerLedger, "sqlite", []),
            EMPTY_CUSTOMER_LEDGER_SQL["sqlite"],
        )

    def test_unsupported_vendor(self):
        with self.assertRaises(NotImplementedError):
            build_ledger_sql(CustomerLedger, "mysql")


class LedgerModelTests(SimpleTestCase):
    def test_one_source_per_table(self):
        self.assertEqual(ledger_sources(CustomerLedger), [CustomerPayment, Movement])
        self.assertEqual(ledger_sources(TreasuryLedger), [TreasuryMovement])

    def test_factory_output(self):
        meta = CustomerLedger._meta
        self.assertTrue(issubclass(CustomerLedger, LedgerModel))
        self.assertFalse(meta.managed)
        self.assertEqual(meta.app_label, "ledger_tests")
        self.assertEqual(meta.db_table, "erp_ledger_ledger_tests_customer")
        self.assertIs(meta.get_field("customer").related_model, Customer)
        self.assertEqual(CustomerLedger.ledger_field, "customer")

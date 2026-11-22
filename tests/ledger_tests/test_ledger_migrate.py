import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError, connection, models
from django.db.models.signals import pre_migrate
from django.test import TransactionTestCase

from erp_framework.ledgers import (
    LEDGER_PREFIX,
    _views_and_tables,
    create_ledger_views,
    drop_ledger_views_before_migrate,
)

from .models import (
    Customer,
    CustomerLedger,
    CustomerPayment,
    Movement,
    Sale,
    Treasury,
    TreasuryLedger,
)

CUSTOMER_VIEW = "erp_ledger_ledger_tests_customer"
TREASURY_VIEW = "erp_ledger_ledger_tests_treasury"
WHEN = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)


def migrate(*args):
    out = StringIO()
    call_command(
        "migrate", "ledger_tests", *args, verbosity=1, interactive=False, stdout=out
    )
    return out.getvalue()


def ledger_views():
    views = _views_and_tables(connection)[0]
    return sorted(v for v in views if v.startswith(LEDGER_PREFIX))


class LedgerMigrateTests(TransactionTestCase):
    available_apps = [
        "django.contrib.contenttypes",
        "django.contrib.auth",
        "erp_framework",
        "ledger_tests",
    ]

    def tearDown(self):
        migrate()
        super().tearDown()

    def stamp(self):
        user, _ = get_user_model().objects.get_or_create(username="clerk")
        return {"owner": user, "lastmod_user": user}

    def test_fresh_migrate_creates_the_views(self):
        migrate("zero")
        self.assertEqual(ledger_views(), [])
        migrate()
        self.assertEqual(ledger_views(), [CUSTOMER_VIEW, TREASURY_VIEW])
        customer = Customer.objects.create(name="Acme", **self.stamp())
        till = Treasury.objects.create(name="Till", **self.stamp())
        Sale.objects.create(customer=customer, value=300, date=WHEN, **self.stamp())
        CustomerPayment.objects.create(
            customer=customer, treasury=till, value=250, date=WHEN, **self.stamp()
        )
        self.assertEqual(
            sorted(CustomerLedger.objects.values_list("type", "value")),
            [("customerpayment", 250), ("sale", 300)],
        )

    def test_partial_migrate_skips_sources_not_migrated_yet(self):
        migrate("zero")
        output = migrate("0001")
        self.assertIn(
            f"Ledger view {CUSTOMER_VIEW} skips ledger_tests.CustomerPayment, ledger_tests.Movement",
            output,
        )
        self.assertEqual(ledger_views(), [CUSTOMER_VIEW, TREASURY_VIEW])
        self.assertEqual(CustomerLedger.objects.count(), 0)
        till = Treasury.objects.create(name="Till", **self.stamp())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO ledger_tests_treasurymovement (slug, date, type, value, treasury_id, owner_id, "
                "lastmod_user_id, creation_date, lastmod) VALUES ('1', %s, 'cashin', 40, %s, %s, %s, %s, %s)",
                [
                    WHEN,
                    till.pk,
                    till.owner_id,
                    till.owner_id,
                    till.lastmod,
                    till.lastmod,
                ],
            )
        self.assertEqual(
            list(TreasuryLedger.objects.values_list("type", "value")), [("cashin", 40)]
        )

        output = migrate()
        self.assertNotIn("skips", output)
        customer = Customer.objects.create(name="Acme", **self.stamp())
        CustomerPayment.objects.create(
            customer=customer, treasury=till, value=250, date=WHEN, **self.stamp()
        )
        self.assertEqual(
            list(CustomerLedger.objects.values_list("type", "value")),
            [("customerpayment", 250)],
        )

    def test_partial_migrate_names_skipped_sources_on_one_line(self):
        migrate("zero")
        output = migrate("0001")
        line = (
            f"  Ledger view {CUSTOMER_VIEW} skips ledger_tests.CustomerPayment, ledger_tests.Movement: "
            "table or column not migrated yet"
        )
        self.assertIn(line, output.splitlines())
        sql = StringIO()
        call_command("rebuild_ledger_views", "--sql", stdout=sql)
        self.assertNotIn("ledger_tests_movement", sql.getvalue())
        self.assertIn('FROM "ledger_tests_treasurymovement"', sql.getvalue())

    def test_alter_of_a_source_table_with_ledgers_present(self):
        customer = Customer.objects.create(name="Acme", **self.stamp())
        Sale.objects.create(customer=customer, value=300, date=WHEN, **self.stamp())
        migrate("0002")  # slug max_length 60 -> 50 on the movement table
        migrate()  # and back to 60
        self.assertEqual(ledger_views(), [CUSTOMER_VIEW, TREASURY_VIEW])
        self.assertEqual(
            list(CustomerLedger.objects.values_list("type", "value")), [("sale", 300)]
        )

    def test_alter_without_the_hook_fails(self):
        """Negative control: the same ALTER fails when the views are not dropped first."""
        create_ledger_views(verbosity=0)
        old_field = Movement._meta.get_field("slug")
        new_field = models.SlugField(max_length=50, blank=True)
        new_field.set_attributes_from_name("slug")
        pre_migrate.disconnect(dispatch_uid="erp_ledger_drop")
        try:
            with self.assertRaises(DatabaseError):
                with connection.schema_editor() as editor:
                    editor.alter_field(Movement, old_field, new_field, strict=True)
        finally:
            pre_migrate.connect(
                drop_ledger_views_before_migrate, dispatch_uid="erp_ledger_drop"
            )
        self.assertEqual(ledger_views(), [CUSTOMER_VIEW, TREASURY_VIEW])

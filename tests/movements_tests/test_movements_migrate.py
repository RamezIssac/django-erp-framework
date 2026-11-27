import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError, connection, models
from django.db.models.signals import pre_migrate
from django.test import TransactionTestCase

from erp_framework.movements import (
    MOVEMENTS_PREFIX,
    _views_and_tables,
    create_movement_views,
    drop_movement_views_before_migrate,
)

from .models import (
    Customer,
    CustomerMovements,
    CustomerPayment,
    Movement,
    Sale,
    Treasury,
    TreasuryMovements,
)

CUSTOMER_VIEW = "erp_movements_movements_tests_customermovements"
TREASURY_VIEW = "erp_movements_movements_tests_treasurymovements"
PROJECT_VIEW = "erp_movements_movements_project_tests_customersales"
ALL_VIEWS = [PROJECT_VIEW, CUSTOMER_VIEW, TREASURY_VIEW]
WHEN = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)


def migrate(*args):
    out = StringIO()
    call_command(
        "migrate", "movements_tests", *args, verbosity=1, interactive=False, stdout=out
    )
    return out.getvalue()


def movement_views():
    views = _views_and_tables(connection)[0]
    return sorted(v for v in views if v.startswith(MOVEMENTS_PREFIX))


class MovementsMigrateTests(TransactionTestCase):
    available_apps = [
        "django.contrib.contenttypes",
        "django.contrib.auth",
        "erp_framework",
        "movements_tests",
        "movements_project_tests",
    ]

    def tearDown(self):
        call_command("migrate", verbosity=0, interactive=False)
        super().tearDown()

    def stamp(self):
        user, _ = get_user_model().objects.get_or_create(username="clerk")
        return {"owner": user, "lastmod_user": user}

    def test_fresh_migrate_creates_the_views(self):
        migrate("zero")
        self.assertEqual(movement_views(), [])
        migrate()
        self.assertEqual(movement_views(), ALL_VIEWS)
        customer = Customer.objects.create(name="Acme", **self.stamp())
        till = Treasury.objects.create(name="Till", **self.stamp())
        Sale.objects.create(customer=customer, value=300, date=WHEN, **self.stamp())
        CustomerPayment.objects.create(
            customer=customer, treasury=till, value=250, date=WHEN, **self.stamp()
        )
        self.assertEqual(
            sorted(CustomerMovements.objects.values_list("type", "value")),
            [("customerpayment", 250), ("sale", 300)],
        )

    def test_partial_migrate_skips_sources_not_migrated_yet(self):
        migrate("zero")
        output = migrate("0001")
        self.assertIn(
            f"Movements view {CUSTOMER_VIEW} skips movements_tests.CustomerPayment, movements_tests.Movement",
            output,
        )
        self.assertEqual(movement_views(), ALL_VIEWS)
        self.assertEqual(CustomerMovements.objects.count(), 0)
        till = Treasury.objects.create(name="Till", **self.stamp())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO movements_tests_treasurymovement (slug, date, type, value, treasury_id, owner_id, "
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
            list(TreasuryMovements.objects.values_list("type", "value")), [("cashin", 40)]
        )

        output = migrate()
        self.assertNotIn("skips", output)
        customer = Customer.objects.create(name="Acme", **self.stamp())
        CustomerPayment.objects.create(
            customer=customer, treasury=till, value=250, date=WHEN, **self.stamp()
        )
        self.assertEqual(
            list(CustomerMovements.objects.values_list("type", "value")),
            [("customerpayment", 250)],
        )

    def test_partial_migrate_names_skipped_sources_on_one_line(self):
        migrate("zero")
        output = migrate("0001")
        line = (
            f"  Movements view {CUSTOMER_VIEW} skips movements_tests.CustomerPayment, movements_tests.Movement: "
            "table or column not migrated yet"
        )
        self.assertIn(line, output.splitlines())
        sql = StringIO()
        call_command("rebuild_movement_views", "--sql", stdout=sql)
        self.assertNotIn("movements_tests_movement", sql.getvalue())
        self.assertIn('FROM "movements_tests_treasurymovement"', sql.getvalue())

    def test_alter_of_a_source_table_with_movement_views_present(self):
        customer = Customer.objects.create(name="Acme", **self.stamp())
        Sale.objects.create(customer=customer, value=300, date=WHEN, **self.stamp())
        migrate("0002")  # slug max_length 60 -> 50 on the movement table
        migrate()  # and back to 60
        self.assertEqual(movement_views(), ALL_VIEWS)
        self.assertEqual(
            list(CustomerMovements.objects.values_list("type", "value")), [("sale", 300)]
        )

    def test_alter_without_the_hook_fails(self):
        """Negative control: the same ALTER fails when the views are not dropped first."""
        create_movement_views(verbosity=0)
        old_field = Movement._meta.get_field("slug")
        new_field = models.SlugField(max_length=50, blank=True)
        new_field.set_attributes_from_name("slug")
        pre_migrate.disconnect(dispatch_uid="erp_movements_drop")
        try:
            with self.assertRaises(DatabaseError):
                with connection.schema_editor() as editor:
                    editor.alter_field(Movement, old_field, new_field, strict=True)
        finally:
            pre_migrate.connect(
                drop_movement_views_before_migrate, dispatch_uid="erp_movements_drop"
            )
        self.assertEqual(movement_views(), ALL_VIEWS)

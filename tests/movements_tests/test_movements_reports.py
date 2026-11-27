import datetime
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.db.models import Q, Sum
from django.test import TestCase
from slick_reporting.fields import ComputationField
from slick_reporting.generator import ReportGenerator

from erp_framework import movements
from erp_framework.doc_types import for_entity
from erp_framework.movements import (
    _migrated_app_configs,
    build_movements_sql,
    create_movement_views,
    create_movement_views_after_migrate,
    drop_movement_views,
    drop_movement_views_before_migrate,
    movements_models,
    present_sources,
)
from erp_framework.management.commands.rebuild_movement_views import Command as RebuildCommand
from erp_framework.reporting.views import ReportView

from .models import (
    CashIn,
    CashOut,
    Customer,
    CustomerMovements,
    Movement,
    CustomerPayment,
    Sale,
    SaleReturn,
    ServiceInvoice,
    Treasury,
    TreasuryMovements,
)
from .test_movements_migrate import ALL_VIEWS, CUSTOMER_VIEW, PROJECT_VIEW, TREASURY_VIEW, movement_views


def at(day):
    return datetime.datetime.combine(
        day, datetime.time(10), tzinfo=datetime.timezone.utc
    )


class CustomerBalance(ReportView):
    """The report shape shown in docs/source/topics/doc_types.rst."""

    base_model = Customer
    report_model = CustomerMovements
    group_by = "customer"
    date_field = "date"
    doc_type_field_name = "type"
    doc_type_plus_list, doc_type_minus_list = for_entity(Customer)
    columns = ["name", "__debit__", "__credit__"]


class MovementsReportTests(TestCase):
    """A customer balance over sales, returns, service invoices and payments from another table."""

    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create(username="clerk", is_staff=True)
        stamp = {"owner": user, "lastmod_user": user}
        cls.acme = Customer.objects.create(name="Acme", **stamp)
        cls.north = Customer.objects.create(name="Northwind", **stamp)
        cls.till = Treasury.objects.create(name="Till", **stamp)
        ServiceInvoice.objects.create(
            customer=cls.acme,
            value=300,
            discount=30,
            quantity=2,
            date=at(datetime.date(2026, 10, 21)),
            **stamp,
        )
        CustomerPayment.objects.create(
            customer=cls.acme,
            treasury=cls.till,
            value=250,
            discount=5,
            date=at(datetime.date(2026, 10, 22)),
            **stamp,
        )
        Sale.objects.create(
            customer=cls.north,
            value=100,
            discount=10,
            quantity=1,
            date=at(datetime.date(2025, 12, 1)),
            **stamp,
        )
        Sale.objects.create(
            customer=cls.north, value=300, quantity=3, date=at(datetime.date(2026, 2, 1)), **stamp
        )
        SaleReturn.objects.create(
            customer=cls.north, value=20, date=at(datetime.date(2026, 2, 1)), **stamp
        )
        CustomerPayment.objects.create(
            customer=cls.north,
            treasury=cls.till,
            value=250,
            date=at(datetime.date(2026, 3, 1)),
            **stamp,
        )
        CashIn.objects.create(
            treasury=cls.till, value=40, date=at(datetime.date(2026, 3, 2)), **stamp
        )
        CashOut.objects.create(
            treasury=cls.till, value=15, date=at(datetime.date(2026, 3, 3)), **stamp
        )

    def debit_credit(self, movements_model, entity):
        # __balance__ is not used: released slick 1.5.1 resolves it as `debit or 0 - credit or 0`.
        doc_types = for_entity(entity)
        report = ReportGenerator(
            report_model=movements_model,
            group_by=entity._meta.model_name,
            date_field="date",
            columns=["name", "__debit__", "__credit__"],
            start_date=at(datetime.date(2025, 1, 1)),
            end_date=at(datetime.date(2026, 11, 21)),
            doc_type_plus_list=[Q(type__in=doc_types.plus)],
            doc_type_minus_list=[Q(type__in=doc_types.minus)],
        )
        return {
            r["name"]: (r["__debit__"], r["__credit__"])
            for r in report.get_report_data()
        }

    def test_views_exist_after_a_fresh_migrate(self):
        self.assertEqual(movement_views(), ALL_VIEWS)

    def test_customer_balance_includes_payments_and_services(self):
        # Acme: service invoice 300, payment 250. Northwind: sales 100 + 300, return 20, payment 250.
        totals = self.debit_credit(CustomerMovements, Customer)
        self.assertEqual(totals, {"Acme": (300, 250), "Northwind": (400, 270)})
        self.assertEqual(
            {name: d - c for name, (d, c) in totals.items()},
            {"Acme": 50, "Northwind": 130},
        )

    def test_numeric_columns_sum_across_source_tables(self):
        # Acme: invoice discount 30 + payment discount 5 (treasury table); the payment has no quantity.
        report = ReportGenerator(
            report_model=CustomerMovements,
            group_by="customer",
            date_field="date",
            columns=[
                "name",
                ComputationField.create(Sum, "discount", name="discount_sum"),
                ComputationField.create(Sum, "quantity", name="quantity_sum"),
            ],
            start_date=at(datetime.date(2025, 1, 1)),
            end_date=at(datetime.date(2026, 11, 21)),
        )
        totals = {r["name"]: (r["discount_sum"], r["quantity_sum"]) for r in report.get_report_data()}
        self.assertEqual(totals, {"Acme": (35, 2), "Northwind": (10, 4)})

    def test_single_table_report_misses_the_payments(self):
        totals = self.debit_credit(Movement, Customer)
        self.assertEqual(totals, {"Acme": (300, 0), "Northwind": (400, 20)})

    def test_treasury_balance_includes_customer_payments(self):
        self.assertEqual(
            self.debit_credit(TreasuryMovements, Treasury), {"Till": (540, 15)}
        )

    def test_documented_report_class_filters_by_the_movement_types(self):
        plus, minus = CustomerBalance().get_doc_types_q_filters()
        self.assertEqual(plus, [Q(type__in=["sale", "serviceinvoice"])])
        self.assertEqual(minus, [Q(type__in=["customerpayment", "salereturn"])])

    def test_statement_is_an_orm_queryset(self):
        rows = CustomerMovements.objects.filter(customer=self.north).order_by(
            "date", "type"
        )
        self.assertEqual(
            [(r.type, r.value) for r in rows],
            [
                ("sale", 100),
                ("sale", 300),
                ("salereturn", 20),
                ("customerpayment", 250),
            ],
        )
        payment = rows.last()
        self.assertEqual(payment.content_type.model, "customerpayment")
        self.assertEqual(CustomerPayment.objects.get(pk=payment.object_id).value, 250)
        self.assertEqual(
            payment.id, f"movements_tests.customerpayment-{payment.object_id}"
        )

    def test_group_by_follows_the_foreign_key(self):
        names = CustomerMovements.objects.values_list(
            "customer__name", flat=True
        ).distinct()
        self.assertEqual(sorted(names), ["Acme", "Northwind"])

    def test_rebuild_command(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE VIEW "erp_movements_retired" AS SELECT 1 AS "id"')
        out = StringIO()
        call_command("rebuild_movement_views", stdout=out)
        self.assertEqual(movement_views(), ALL_VIEWS)
        self.assertIn(
            "Rebuilt erp_movements_movements_tests_customermovements over 2 source table(s).",
            out.getvalue(),
        )
        self.assertEqual(CustomerMovements.objects.count(), 6)

    def test_rebuild_command_reports_each_view_on_its_own_line(self):
        out = StringIO()
        call_command("rebuild_movement_views", stdout=out)
        self.assertIn("Rebuilt erp_movements_movements_tests_treasurymovements over 1 source table(s).", out.getvalue().splitlines())
        self.assertTrue(RebuildCommand.help)

    def test_rebuild_command_sql_is_each_view_over_its_present_sources(self):
        out = StringIO()
        call_command("rebuild_movement_views", "--sql", stdout=out)
        expected = "".join(
            build_movements_sql(movements_model, connection, present_sources(movements_model, connection)[0]) + ";\n"
            for movements_model in movements_models()
        )
        self.assertEqual(out.getvalue(), expected)
        self.assertIn('FROM "movements_tests_movement"', expected)

    def test_drop_keeps_other_views(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE VIEW "reporting_snapshot" AS SELECT 1 AS "id"')
        self.assertEqual(drop_movement_views(), ALL_VIEWS)
        self.assertIn("reporting_snapshot", movements._views_and_tables(connection)[0])

    def test_drop_removes_views_under_the_legacy_ledger_name(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE VIEW "erp_ledger_movements_tests_customer" AS SELECT 1 AS "id"')
        self.assertEqual(
            drop_movement_views(),
            ["erp_ledger_movements_tests_customer", *ALL_VIEWS],
        )
        self.assertEqual(movements._views_and_tables(connection)[0] & {"erp_ledger_movements_tests_customer"}, set())

    def test_create_output_by_verbosity(self):
        for verbosity, lines in (
            (None, []),
            (1, []),
            (2, [f"  Movements view {PROJECT_VIEW}: 2 source table(s)", f"  Movements view {CUSTOMER_VIEW}: 2 source table(s)", f"  Movements view {TREASURY_VIEW}: 1 source table(s)"]),
        ):
            with self.subTest(verbosity=verbosity):
                out = StringIO()
                kwargs = {} if verbosity is None else {"verbosity": verbosity}
                create_movement_views(stdout=out, **kwargs)
                self.assertEqual(out.getvalue().splitlines(), lines)

    def test_create_skips_one_view_and_keeps_going(self):
        allow_migrate = movements.router.allow_migrate

        def no_customer_movements(using, app_label, **hints):
            return hints.get("model_name") != "customermovements" and allow_migrate(using, app_label, **hints)

        views_and_tables = movements._views_and_tables

        def no_customer_table(connection):
            views, tables = views_and_tables(connection)
            return views, tables - {Customer._meta.db_table}

        for patch, expected in (
            (mock.patch.object(movements.router, "allow_migrate", no_customer_movements), [PROJECT_VIEW, TREASURY_VIEW]),
            (mock.patch.object(movements, "_views_and_tables", no_customer_table), [TREASURY_VIEW]),
        ):
            with self.subTest(patch=patch.attribute), patch:
                created = create_movement_views(verbosity=0)
                self.assertEqual([name for name, _present, _missing in created], expected)

    def test_migrate_receivers_run_once_per_command(self):
        configs = _migrated_app_configs()
        for sender, plan in ((configs[1], []), (configs[0], None)):
            drop_movement_views_before_migrate(sender, "default", plan=plan)
            self.assertEqual(movement_views(), ALL_VIEWS)
        drop_movement_views_before_migrate(configs[0], "default", plan=[])
        self.assertEqual(movement_views(), [])
        out = StringIO()
        for sender, plan in ((configs[-2], []), (configs[1], []), (configs[-1], None)):
            create_movement_views_after_migrate(sender, "default", plan=plan, stdout=out)
            self.assertEqual(movement_views(), [])
        create_movement_views_after_migrate(configs[-1], "default", plan=[], stdout=out)
        self.assertEqual(movement_views(), ALL_VIEWS)
        self.assertEqual(out.getvalue(), "")

    def test_migrate_receivers_are_connected_once(self):
        from django.db.models.signals import post_migrate, pre_migrate

        for signal, receiver, uid in (
            (pre_migrate, drop_movement_views_before_migrate, "erp_movements_drop"),
            (post_migrate, create_movement_views_after_migrate, "erp_movements_create"),
        ):
            with self.subTest(uid=uid):
                self.assertTrue(signal.disconnect(dispatch_uid=uid))
                self.addCleanup(signal.connect, receiver, dispatch_uid=uid)

    def test_rebuild_command_prints_sql(self):
        out = StringIO()
        call_command("rebuild_movement_views", "--sql", stdout=out)
        self.assertIn(
            'CREATE VIEW "erp_movements_movements_tests_treasurymovements" AS', out.getvalue()
        )

    def test_migration_state_matches_the_factory(self):
        call_command(
            "makemigrations", "movements_tests", "--check", "--dry-run", stdout=StringIO()
        )

import datetime
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.db.models import Q
from django.test import TestCase
from slick_reporting.generator import ReportGenerator

from erp_framework import ledgers
from erp_framework.doc_types import for_entity
from erp_framework.ledgers import (
    _migrated_app_configs,
    build_ledger_sql,
    create_ledger_views,
    create_ledger_views_after_migrate,
    drop_ledger_views,
    drop_ledger_views_before_migrate,
    present_sources,
)
from erp_framework.management.commands.rebuild_ledger_views import Command as RebuildCommand
from erp_framework.reporting.views import ReportView

from .models import (
    CashIn,
    CashOut,
    Customer,
    CustomerLedger,
    Movement,
    CustomerPayment,
    Sale,
    SaleReturn,
    ServiceInvoice,
    Treasury,
    TreasuryLedger,
)
from .test_ledger_migrate import CUSTOMER_VIEW, TREASURY_VIEW, ledger_views


def at(day):
    return datetime.datetime.combine(
        day, datetime.time(10), tzinfo=datetime.timezone.utc
    )


class CustomerBalance(ReportView):
    """The report shape shown in docs/source/topics/doc_types.rst."""

    base_model = Customer
    report_model = CustomerLedger
    group_by = "customer"
    date_field = "date"
    doc_type_field_name = "type"
    doc_type_plus_list, doc_type_minus_list = for_entity(Customer)
    columns = ["name", "__debit__", "__credit__"]


class LedgerReportTests(TestCase):
    """A customer balance over sales, returns, service invoices and payments from another table."""

    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create(username="clerk", is_staff=True)
        stamp = {"owner": user, "lastmod_user": user}
        cls.acme = Customer.objects.create(name="Acme", **stamp)
        cls.north = Customer.objects.create(name="Northwind", **stamp)
        cls.till = Treasury.objects.create(name="Till", **stamp)
        ServiceInvoice.objects.create(
            customer=cls.acme, value=300, date=at(datetime.date(2026, 10, 21)), **stamp
        )
        CustomerPayment.objects.create(
            customer=cls.acme,
            treasury=cls.till,
            value=250,
            date=at(datetime.date(2026, 10, 22)),
            **stamp,
        )
        Sale.objects.create(
            customer=cls.north, value=100, date=at(datetime.date(2025, 12, 1)), **stamp
        )
        Sale.objects.create(
            customer=cls.north, value=300, date=at(datetime.date(2026, 2, 1)), **stamp
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

    def debit_credit(self, ledger, entity):
        # __balance__ is not used: released slick 1.5.1 resolves it as `debit or 0 - credit or 0`.
        doc_types = for_entity(entity)
        report = ReportGenerator(
            report_model=ledger,
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
        self.assertEqual(ledger_views(), [CUSTOMER_VIEW, TREASURY_VIEW])

    def test_customer_balance_includes_payments_and_services(self):
        # Acme: service invoice 300, payment 250. Northwind: sales 100 + 300, return 20, payment 250.
        totals = self.debit_credit(CustomerLedger, Customer)
        self.assertEqual(totals, {"Acme": (300, 250), "Northwind": (400, 270)})
        self.assertEqual(
            {name: d - c for name, (d, c) in totals.items()},
            {"Acme": 50, "Northwind": 130},
        )

    def test_single_table_report_misses_the_payments(self):
        totals = self.debit_credit(Movement, Customer)
        self.assertEqual(totals, {"Acme": (300, 0), "Northwind": (400, 20)})

    def test_treasury_balance_includes_customer_payments(self):
        self.assertEqual(
            self.debit_credit(TreasuryLedger, Treasury), {"Till": (540, 15)}
        )

    def test_documented_report_class_filters_by_the_ledger_types(self):
        plus, minus = CustomerBalance().get_doc_types_q_filters()
        self.assertEqual(plus, [Q(type__in=["sale", "serviceinvoice"])])
        self.assertEqual(minus, [Q(type__in=["customerpayment", "salereturn"])])

    def test_statement_is_an_orm_queryset(self):
        rows = CustomerLedger.objects.filter(customer=self.north).order_by(
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
            payment.id, f"ledger_tests.customerpayment-{payment.object_id}"
        )

    def test_group_by_follows_the_foreign_key(self):
        names = CustomerLedger.objects.values_list(
            "customer__name", flat=True
        ).distinct()
        self.assertEqual(sorted(names), ["Acme", "Northwind"])

    def test_rebuild_command(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE VIEW "erp_ledger_retired" AS SELECT 1 AS "id"')
        out = StringIO()
        call_command("rebuild_ledger_views", stdout=out)
        self.assertEqual(ledger_views(), [CUSTOMER_VIEW, TREASURY_VIEW])
        self.assertIn(
            "Rebuilt erp_ledger_ledger_tests_customer over 2 source table(s).",
            out.getvalue(),
        )
        self.assertEqual(CustomerLedger.objects.count(), 6)

    def test_rebuild_command_reports_each_view_on_its_own_line(self):
        out = StringIO()
        call_command("rebuild_ledger_views", stdout=out)
        self.assertIn("Rebuilt erp_ledger_ledger_tests_treasury over 1 source table(s).", out.getvalue().splitlines())
        self.assertTrue(RebuildCommand.help)

    def test_rebuild_command_sql_is_each_view_over_its_present_sources(self):
        out = StringIO()
        call_command("rebuild_ledger_views", "--sql", stdout=out)
        expected = "".join(
            build_ledger_sql(ledger, connection, present_sources(ledger, connection)[0]) + ";\n"
            for ledger in (CustomerLedger, TreasuryLedger)
        )
        self.assertEqual(out.getvalue(), expected)
        self.assertIn('FROM "ledger_tests_movement"', expected)

    def test_drop_keeps_other_views(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE VIEW "reporting_snapshot" AS SELECT 1 AS "id"')
        self.assertEqual(drop_ledger_views(), [CUSTOMER_VIEW, TREASURY_VIEW])
        self.assertIn("reporting_snapshot", ledgers._views_and_tables(connection)[0])

    def test_create_output_by_verbosity(self):
        for verbosity, lines in (
            (None, []),
            (1, []),
            (2, [f"  Ledger view {CUSTOMER_VIEW}: 2 source table(s)", f"  Ledger view {TREASURY_VIEW}: 1 source table(s)"]),
        ):
            with self.subTest(verbosity=verbosity):
                out = StringIO()
                kwargs = {} if verbosity is None else {"verbosity": verbosity}
                create_ledger_views(stdout=out, **kwargs)
                self.assertEqual(out.getvalue().splitlines(), lines)

    def test_create_skips_one_ledger_and_keeps_going(self):
        allow_migrate = ledgers.router.allow_migrate

        def no_customer_ledger(using, app_label, **hints):
            return hints.get("model_name") != "customerledger" and allow_migrate(using, app_label, **hints)

        views_and_tables = ledgers._views_and_tables

        def no_customer_table(connection):
            views, tables = views_and_tables(connection)
            return views, tables - {Customer._meta.db_table}

        for patch in (
            mock.patch.object(ledgers.router, "allow_migrate", no_customer_ledger),
            mock.patch.object(ledgers, "_views_and_tables", no_customer_table),
        ):
            with self.subTest(patch=patch.attribute), patch:
                created = create_ledger_views(verbosity=0)
                self.assertEqual([name for name, _present, _missing in created], [TREASURY_VIEW])

    def test_migrate_receivers_run_once_per_command(self):
        configs = _migrated_app_configs()
        for sender, plan in ((configs[1], []), (configs[0], None)):
            drop_ledger_views_before_migrate(sender, "default", plan=plan)
            self.assertEqual(ledger_views(), [CUSTOMER_VIEW, TREASURY_VIEW])
        drop_ledger_views_before_migrate(configs[0], "default", plan=[])
        self.assertEqual(ledger_views(), [])
        out = StringIO()
        for sender, plan in ((configs[-2], []), (configs[1], []), (configs[-1], None)):
            create_ledger_views_after_migrate(sender, "default", plan=plan, stdout=out)
            self.assertEqual(ledger_views(), [])
        create_ledger_views_after_migrate(configs[-1], "default", plan=[], stdout=out)
        self.assertEqual(ledger_views(), [CUSTOMER_VIEW, TREASURY_VIEW])
        self.assertEqual(out.getvalue(), "")

    def test_migrate_receivers_are_connected_once(self):
        from django.db.models.signals import post_migrate, pre_migrate

        for signal, receiver, uid in (
            (pre_migrate, drop_ledger_views_before_migrate, "erp_ledger_drop"),
            (post_migrate, create_ledger_views_after_migrate, "erp_ledger_create"),
        ):
            with self.subTest(uid=uid):
                self.assertTrue(signal.disconnect(dispatch_uid=uid))
                self.addCleanup(signal.connect, receiver, dispatch_uid=uid)

    def test_rebuild_command_prints_sql(self):
        out = StringIO()
        call_command("rebuild_ledger_views", "--sql", stdout=out)
        self.assertIn(
            'CREATE VIEW "erp_ledger_ledger_tests_treasury" AS', out.getvalue()
        )

    def test_migration_state_matches_the_factory(self):
        call_command(
            "makemigrations", "ledger_tests", "--check", "--dry-run", stdout=StringIO()
        )

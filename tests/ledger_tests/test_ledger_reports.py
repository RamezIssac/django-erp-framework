import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.db.models import Q
from django.test import TestCase
from slick_reporting.generator import ReportGenerator

from erp_framework.doc_types import for_entity
from erp_framework.reporting.views import ReportView

from .models import (
    CashIn,
    CashOut,
    Customer,
    CustomerLedger,
    CustomerPayment,
    Sale,
    SaleReturn,
    ServiceInvoice,
    Treasury,
    TreasuryLedger,
)


def at(day):
    return datetime.datetime.combine(
        day, datetime.time(10), tzinfo=datetime.timezone.utc
    )


def ledger_view_names():
    with connection.cursor() as cursor:
        tables = connection.introspection.get_table_list(cursor)
    return sorted(
        t.name for t in tables if t.type == "v" and t.name.startswith("erp_ledger_")
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
        self.assertEqual(
            ledger_view_names(),
            ["erp_ledger_ledger_tests_customer", "erp_ledger_ledger_tests_treasury"],
        )

    def test_customer_balance_includes_payments_and_services(self):
        # Acme: service invoice 300, payment 250. Northwind: sales 100 + 300, return 20, payment 250.
        totals = self.debit_credit(CustomerLedger, Customer)
        self.assertEqual(totals, {"Acme": (300, 250), "Northwind": (400, 270)})
        self.assertEqual(
            {name: d - c for name, (d, c) in totals.items()},
            {"Acme": 50, "Northwind": 130},
        )

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
        self.assertEqual(
            ledger_view_names(),
            ["erp_ledger_ledger_tests_customer", "erp_ledger_ledger_tests_treasury"],
        )
        self.assertIn(
            "Rebuilt erp_ledger_ledger_tests_customer over 2 source table(s).",
            out.getvalue(),
        )
        self.assertEqual(CustomerLedger.objects.count(), 6)

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

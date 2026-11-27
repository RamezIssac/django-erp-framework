import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Sum
from django.test import SimpleTestCase, TestCase
from movements_tests.models import Customer, CustomerMovements, Sale, SaleReturn, ServiceInvoice
from movements_tests.test_movements_migrate import ALL_VIEWS, movement_views
from movements_tests.test_movements_sql import BACKENDS, backend_connection
from slick_reporting.fields import ComputationField
from slick_reporting.generator import ReportGenerator

from erp_framework.movements import build_movements_sql, movement_sources
from erp_framework.reporting.registry import ReportRegistry
from erp_framework.reporting.views import ReportView

from .models import CustomerSales

# sources=[Sale, SaleReturn]; units maps Sale.quantity (on the Movement parent) and SaleReturn.returned_units.
CUSTOMER_SALES_SQL = """\
CREATE VIEW "erp_movements_movements_project_tests_customersales" AS
SELECT 'movements_tests.sale-' || CAST(s0."movement_ptr_id" AS TEXT) AS "id",
       s0p1."date" AS "date",
       s0p1."slug" AS "slug",
       s0p1."type" AS "type",
       s0p1."value" AS "value",
       (SELECT "id" FROM "django_content_type" WHERE "app_label" = 'movements_tests' AND "model" = 'sale') AS "content_type_id",
       CAST(s0."movement_ptr_id" AS TEXT) AS "object_id",
       s0p1."customer_id" AS "customer_id",
       s0p1."quantity" AS "units",
       s0p1."discount" AS "discount"
FROM "movements_tests_sale" s0
JOIN "movements_tests_movement" s0p1 ON s0p1."id" = s0."movement_ptr_id"
WHERE s0p1."customer_id" IS NOT NULL
UNION ALL
SELECT 'movements_tests.salereturn-' || CAST(s1."movement_ptr_id" AS TEXT) AS "id",
       s1p1."date" AS "date",
       s1p1."slug" AS "slug",
       s1p1."type" AS "type",
       s1p1."value" AS "value",
       (SELECT "id" FROM "django_content_type" WHERE "app_label" = 'movements_tests' AND "model" = 'salereturn') AS "content_type_id",
       CAST(s1."movement_ptr_id" AS TEXT) AS "object_id",
       s1p1."customer_id" AS "customer_id",
       s1."returned_units" AS "units",
       s1p1."discount" AS "discount"
FROM "movements_tests_salereturn" s1
JOIN "movements_tests_movement" s1p1 ON s1p1."id" = s1."movement_ptr_id"
WHERE s1p1."customer_id" IS NOT NULL"""

WHEN = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)


class CustomerBalance(ReportView):
    report_model = CustomerMovements
    report_title = "Customer balance"
    group_by = "customer"
    date_field = "date"
    columns = ["name", "__total__"]


class CustomerUnits(ReportView):
    report_model = CustomerSales
    report_title = "Customer units"
    group_by = "customer"
    date_field = "date"
    columns = ["name", ComputationField.create(Sum, "units", name="units_sum")]


class ProjectMovementsModelTests(SimpleTestCase):
    def test_view_belongs_to_the_defining_app(self):
        meta = CustomerSales._meta
        self.assertEqual((meta.app_label, meta.db_table), ("movements_project_tests", ALL_VIEWS[0]))
        self.assertIs(CustomerSales.movements_entity, Customer)

    def test_declared_sources_and_mapped_columns(self):
        self.assertEqual(movement_sources(CustomerSales), [Sale, SaleReturn])
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                sql = build_movements_sql(CustomerSales, backend_connection(backend))
                self.assertEqual(sql, CUSTOMER_SALES_SQL)

    def test_reports_on_any_movements_model_of_an_entity_share_its_group(self):
        class ExplicitBase(ReportView):
            base_model = CustomerSales
            report_model = CustomerSales
            report_title = "Explicit base"

        registry = ReportRegistry()
        for report in (CustomerBalance, CustomerUnits, ExplicitBase):
            registry.register(report, ["site"])
        self.assertEqual({r.base_model for r in (CustomerBalance, CustomerUnits, ExplicitBase)}, {Customer})
        self.assertEqual(
            registry.get_base_models_with_reports("site"),
            [(Customer._meta, [CustomerBalance, CustomerUnits, ExplicitBase])],
        )
        self.assertIs(registry.get("customer", CustomerUnits.get_report_slug(), "site"), CustomerUnits)


class ProjectMovementsDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create(username="clerk")
        stamp = {"owner": user, "lastmod_user": user, "date": WHEN}
        cls.acme = Customer.objects.create(name="Acme", owner=user, lastmod_user=user)
        Sale.objects.create(customer=cls.acme, value=100, quantity=4, **stamp)
        ServiceInvoice.objects.create(customer=cls.acme, value=50, quantity=1, **stamp)
        SaleReturn.objects.create(customer=cls.acme, value=20, quantity=9, returned_units=2, **stamp)

    def test_views_side_by_side_after_migrate_and_rebuild(self):
        self.assertEqual(movement_views(), ALL_VIEWS)
        call_command("rebuild_movement_views", stdout=StringIO())
        self.assertEqual(movement_views(), ALL_VIEWS)
        self.assertEqual(CustomerSales.objects.count(), 3)
        self.assertEqual(CustomerMovements.objects.count(), 3)

    def test_units_sum_across_the_two_source_tables(self):
        # Sale 4 and its service invoice child 1 (Sale table), return 2 (its own returned_units, not quantity 9).
        report = ReportGenerator(
            report_model=CustomerSales,
            group_by="customer",
            date_field="date",
            columns=CustomerUnits.columns,
            start_date=WHEN - datetime.timedelta(days=1),
            end_date=WHEN + datetime.timedelta(days=1),
        )
        self.assertEqual([(r["name"], r["units_sum"]) for r in report.get_report_data()], [("Acme", 7)])

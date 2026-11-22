"""MCP report tools (erp_framework.reporting.mcp) over the registered test reports."""

import importlib.util
import json
import sys
import unittest
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Permission
from django.core.exceptions import NON_FIELD_ERRORS, PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase, override_settings

from erp_framework.reporting.models import UserReportPermission

from .admin import ClientAdmin, ProductAdmin, SimpleSalesAdmin
from .models import Client, Product, RushOrder, SimpleSales
from .reports import ClientDetailedStatement, ClientTotalBalance
from .tests import BaseTestData, year

HAS_ADMIN_API = importlib.util.find_spec("admin_api") is not None
PRODUCT_TOKEN = type("Token", (), {"scopes": ["reporting_tests.product:view"], "prefix": "t"})()


@unittest.skipUnless(HAS_ADMIN_API, "needs django-admin-api-mcp")
@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class ReportToolsTests(BaseTestData, TestCase):
    def call(self, name, arguments=None, user=None, token=None, site=None):
        from erp_framework.api import erp_mcp_site

        request = RequestFactory().post("/mcp/")
        request.user = user or self.user
        if token is not None:
            request.api_token = token
        result = (site or erp_mcp_site).call_tool(request, name, arguments or {})
        return result.data, result.is_error

    def run_report(self, report, params=None, site=None, **kwargs):
        out, err = self.call("run_report", {"report": report, "params": params or {}, **kwargs}, site=site)
        self.assertFalse(err, out)
        return out

    def column_names(self, out):
        return [c["name"] for c in out["columns"]]

    def test_tools_are_listed_read_only(self):
        from erp_framework.api import erp_mcp_site
        from erp_framework.reporting.mcp import REPORT_TOOL_NAMES

        tools = {t.name: t for t in erp_mcp_site.get_tools()}
        for name in REPORT_TOOL_NAMES:
            self.assertTrue(tools[name].annotations["readOnlyHint"], name)
            self.assertFalse(tools[name].writes, name)

    def test_list_reports_entry_carries_params_and_balance(self):
        fields = [
            "title", "description", "base_model", "base_model_name", "kind", "shape", "date_filter", "balance", "columns",
            "dates",
        ]
        out, err = self.call("list_reports", {"fields": fields})
        self.assertFalse(err, out)
        reports = {r["report"]: r for r in out["reports"]}
        self.assertEqual(
            reports["client.balances"],
            {
                "report": "client.balances",
                "title": "Clients Balances",
                "description": "Clients Balances",
                "question": "Clients Balances",
                "base_model": "reporting_tests.client",
                "base_model_name": "Client",
                "kind": "group",
                "shape": "by client",
                "date_filter": False,
                "params": {"client_id": "reporting_tests.client", "product_id": "reporting_tests.product"},
                "balance": True,
                "columns": ["Identifier slug", "Name", "Closing Total", "Sum of value"],
                "order_by": {"__balance__": "Closing Total", "__total__": "Sum of value"},
                "dates": "all",
            },
        )
        self.assertEqual(reports["client.clientsalesmonthlyseries"]["dates"], f"{year}-01-01 to today")
        self.assertEqual(reports["client.clientsalesmonthlyseries"]["shape"], "by client monthly")
        self.assertEqual(reports["product.productclientsalesmatrix"]["shape"], "by client x client")
        self.assertEqual(reports["client.clientdetailedstatement"]["shape"], "list")
        self.assertFalse(reports["client.clientdetailedstatement"]["balance"])
        self.assertEqual(reports["client.clientdetailedstatement"]["order_by"], {})
        self.assertTrue(reports["product.productsalesmonthlyseries"]["balance"])
        # owner_id and lastmod_user_id pick users, a model resolve_entities skips (excluded_models)
        self.assertEqual(
            reports["client.client_sales_of_products"]["params"],
            {"client_id": "reporting_tests.client", "product_id": "reporting_tests.product"},
        )
        self.assertEqual(reports["product.productclientsalesmatrix"]["kind"], "crosstab")
        self.assertEqual(reports["client.clientsalesmonthlyseries"]["kind"], "series")
        self.assertEqual(reports["client.clientdetailedstatement"]["kind"], "list")

    def test_describe_report(self):
        out, err = self.call("describe_report", {"report": "product.productclientsalesmatrix"})
        self.assertFalse(err, out)
        self.assertEqual(out["kind"], "crosstab")
        self.assertEqual((out["base_model_name"], out["report_model_name"]), ("Product", "Sale"))
        self.assertEqual(out["crosstab_field"], "client")
        self.assertEqual(out["group_by"], "client")
        self.assertEqual(out["columns"], ["slug", "name"])
        properties = out["params_schema"]["properties"]
        self.assertEqual(properties["client_id"]["x-related-model"], "reporting_tests.client")
        self.assertIn("crosstab_compute_remainder", properties)

    def test_run_group_report_with_filter(self):
        out = self.run_report("client.balances", {"client_id": [self.client1.pk]})
        self.assertEqual(self.column_names(out), ["slug", "name", "__balance__", "__total__"])
        self.assertEqual(out["row_count"], 1)
        self.assertEqual(out["rows"][0][1], "Client 1")
        self.assertFalse(out["truncated"])

    def test_totals_cover_all_rows_when_truncated(self):
        full = self.run_report("client.balances")
        truncated = self.run_report("client.balances", max_rows=1)
        self.assertGreater(full["row_count"], 1)
        self.assertEqual(len(truncated["rows"]), 1)
        self.assertTrue(truncated["truncated"])
        self.assertEqual(truncated["row_count"], full["row_count"])
        self.assertEqual(truncated["totals"], full["totals"])

    def test_run_time_series_report_with_date_range(self):
        out = self.run_report(
            "client.clientsalesmonthlyseries",
            {"client_id": [self.client1.pk], "start_date": f"{year}-02-01", "end_date": f"{year}-03-31"},
        )
        # A period column is keyed by the period's end: February ends {year}-03-01, March {year}-04-01.
        periods = {n.split("TS")[1] for n in self.column_names(out) if "TS" in n}
        self.assertEqual(periods, {f"{year}0301", f"{year}0401"})
        self.assertEqual(out["row_count"], 1)

    def test_run_crosstab_report(self):
        out = self.run_report("product.productclientsalesmatrix", {"client_id": [self.client1.pk]})
        self.assertIn(f"__total__CT{self.client1.pk}", self.column_names(out))
        self.assertIn("__total__CT----", self.column_names(out))

    def test_run_list_report_honors_date_range(self):
        out = self.run_report(
            "client.clientdatedstatement", {"start_date": f"{year}-02-01", "end_date": f"{year}-02-28"}
        )
        date_index = self.column_names(out).index("date")
        self.assertEqual(out["row_count"], 3)
        self.assertTrue(all(row[date_index].startswith(f"{year}-02") for row in out["rows"]), out["rows"])

    def test_unknown_param_is_invalid(self):
        out, err = self.call("run_report", {"report": "client.balances", "params": {"client": [self.client1.pk]}})
        self.assertTrue(err)
        self.assertEqual(out["error"], "invalid_params")

    def test_bad_value_returns_field_errors(self):
        out, err = self.call("run_report", {"report": "client.balances", "params": {"client_id": ["x"]}})
        self.assertTrue(err)
        self.assertEqual(out["error"], "invalid_params")
        self.assertIn("client_id", out["fields"])

    def test_max_rows_above_cap_is_capped(self):
        from erp_framework.api import ERPMcpSite, erp_api_site

        class OneRowSite(ERPMcpSite):
            report_max_rows_cap = 1

        out = self.run_report("client.balances", max_rows=10_000, site=OneRowSite(erp_api_site, name="one_row_mcp"))
        self.assertEqual(len(out["rows"]), 1)
        self.assertTrue(out["truncated"])

    def test_foreign_key_param_hidden_by_the_admin_is_refused(self):
        one_client = Client.objects.filter(pk=self.client1.pk)
        with mock.patch.object(ClientAdmin, "get_queryset", lambda admin, request: one_client):
            out, err = self.call("run_report", {"report": "client.balances", "params": {"client_id": [self.client2.pk]}})
            self.assertTrue(err, out)
            self.assertEqual(out["error"], "invalid_params")
            self.assertIn("client_id", out["fields"])
            out = self.run_report("client.balances", {"client_id": [self.client1.pk]})
        self.assertEqual([row[1] for row in out["rows"]], ["Client 1"])

    def test_instructions_route_questions_to_reports(self):
        from erp_framework.api import erp_mcp_site

        instructions = erp_mcp_site.instructions
        self.assertIn("7. Reports: run_report's description lists the reports you may run", instructions)
        self.assertIn("passing resolve_entities IDs as lists", instructions)
        self.assertIn("when none fits, run_dynamic_report", instructions)
        self.assertIn("Note: run the report for a kind of record ('sales by client')", instructions)
        self.assertIn("Note: answer totals and balances with a report, not summed list_objects rows", instructions)
        self.assertNotIn("look them up with list_objects", instructions)
        for item in ("1.", "2.", "3.", "4.", "5.", "6.", "7."):
            self.assertEqual(instructions.count(f"\n{item} "), 1, item)
        self.assertNotIn("\n8. ", instructions)
        self.assertNotIn("primary key", instructions)

    def test_resolved_id_runs_the_report_within_the_admin_scope(self):
        one_client = Client.objects.filter(pk=self.client1.pk)
        with mock.patch.object(ClientAdmin, "get_queryset", lambda admin, request: one_client):
            out, err = self.call(
                "resolve_entities", {"terms": [{"text": "client", "models": ["reporting_tests.client"]}]}
            )
            self.assertFalse(err, out)
            objects = out["results"][0]["objects"]
            self.assertEqual(objects["status"], "unique", objects)
            self.assertEqual([c["id"] for c in objects["candidates"]], [self.client1.pk])

            report = self.run_report("client.balances", {"client_id": [objects["candidates"][0]["id"]]})
        self.assertEqual([row[1] for row in report["rows"]], ["Client 1"])

    def test_order_by_and_max_rows_give_a_top_n(self):
        balance = self.column_names(self.run_report("client.balances")).index("__balance__")
        full = self.run_report("client.balances")["rows"]
        by_balance = sorted(full, key=lambda row: Decimal(row[balance]), reverse=True)
        top = self.run_report("client.balances", order_by="-__balance__", max_rows=2)
        self.assertEqual(top["rows"], by_balance[:2])
        self.assertTrue(top["truncated"])
        self.assertEqual(top["row_count"], len(full))
        lowest = self.run_report("client.balances", order_by="__balance__", max_rows=1)
        self.assertEqual(lowest["rows"], by_balance[-1:])

    def test_order_by_is_checked_against_the_report_keys(self):
        out, err = self.call("run_report", {"report": "client.balances", "order_by": "-name"})
        self.assertTrue(err)
        self.assertEqual(out["error"], "invalid_params")
        self.assertEqual(
            out["fields"]["order_by"][0]["message"],
            "Sort by one of: __balance__, __total__; prefix '-' for highest first.",
        )
        out, err = self.call("run_report", {"report": "client.clientdetailedstatement", "order_by": "value"})
        self.assertTrue(err)
        self.assertEqual(out["fields"]["order_by"][0]["message"], "This report cannot be sorted.")

    def test_single_id_runs_like_a_list(self):
        out = self.run_report("client.balances", {"client_id": self.client1.pk})
        self.assertEqual([row[1] for row in out["rows"]], ["Client 1"])

    def test_unknown_report_is_not_found(self):
        out, err = self.call("run_report", {"report": "client.nope"})
        self.assertTrue(err)
        self.assertEqual(out["error"], "not_found")

    def test_user_without_view_permission_sees_no_reports(self):
        out, err = self.call("list_reports", user=self.limited_user)
        self.assertFalse(err, out)
        self.assertEqual(out["reports"], [])
        out, err = self.call("run_report", {"report": "client.balances"}, user=self.limited_user)
        self.assertTrue(err)
        self.assertEqual(out["error"], "not_found")

    def test_report_permission_row_grants_one_report(self):
        UserReportPermission.objects.create(
            user=self.limited_user, report_code=ClientTotalBalance.get_report_code(), view=True
        )
        out, err = self.call("list_reports", user=self.limited_user)
        self.assertFalse(err, out)
        self.assertEqual([r["report"] for r in out["reports"]], ["client.balances"])

    def test_model_view_permission_grants_its_reports(self):
        self.limited_user.user_permissions.add(Permission.objects.get(codename="view_client"))
        out, err = self.call("list_reports", {"fields": ["base_model"]}, user=self.limited_user)
        self.assertFalse(err, out)
        self.assertTrue(out["reports"])
        self.assertTrue(all(r["base_model"] == "reporting_tests.client" for r in out["reports"]))

    def test_token_scope_narrows_reports(self):
        out, err = self.call("list_reports", {"fields": ["base_model"]}, token=PRODUCT_TOKEN)
        self.assertFalse(err, out)
        self.assertTrue(out["reports"])
        self.assertTrue(all(r["base_model"] == "reporting_tests.product" for r in out["reports"]))

    def test_token_scope_checks_report_model_without_base_model(self):
        with mock.patch.object(ClientTotalBalance, "base_model", None):
            out, err = self.call("list_reports", {"fields": ["base_model"]}, token=PRODUCT_TOKEN)
        self.assertFalse(err, out)
        self.assertTrue(all(r["base_model"] == "reporting_tests.product" for r in out["reports"]), out["reports"])

    def test_is_report_exposed_hides_reports(self):
        from erp_framework.api import ERPMcpSite, erp_api_site

        class ProductOnlySite(ERPMcpSite):
            def is_report_exposed(self, report_class):
                return report_class.get_base_model_name() == "product"

        out, err = self.call("list_reports", site=ProductOnlySite(erp_api_site, name="product_only_mcp"))
        self.assertFalse(err, out)
        self.assertTrue(all(r["report"].startswith("product.") for r in out["reports"]))

    def test_report_tool_input_schemas(self):
        from erp_framework.api import erp_mcp_site
        from erp_framework.reporting.mcp import SPEC_SCHEMA

        schemas = {t.name: t.input_schema for t in erp_mcp_site.get_tools()}
        max_rows = {"type": "integer", "minimum": 1, "maximum": 1000, "default": 50}
        self.assertEqual(set(schemas["list_reports"]["properties"]), {"fields"})
        self.assertEqual(schemas["list_reports"]["properties"]["fields"]["type"], "array")
        self.assertEqual(schemas["describe_report"]["required"], ["report"])
        self.assertEqual(schemas["describe_report"]["properties"]["report"]["type"], "string")
        self.assertIn("description", schemas["describe_report"]["properties"]["report"])
        run = schemas["run_report"]
        self.assertEqual(run["required"], ["report"])
        self.assertEqual(set(run["properties"]), {"report", "params", "order_by", "max_rows"})
        self.assertEqual(run["properties"]["params"]["type"], "object")
        self.assertEqual(run["properties"]["order_by"]["type"], "string")
        self.assertIn("description", run["properties"]["order_by"])
        self.assertIn("description", run["properties"]["params"])
        self.assertEqual({k: run["properties"]["max_rows"][k] for k in max_rows}, max_rows)
        self.assertIn("description", run["properties"]["max_rows"])
        dynamic = schemas["run_dynamic_report"]
        self.assertEqual(dynamic["required"], ["spec"])
        self.assertEqual(dynamic["properties"]["max_rows"], run["properties"]["max_rows"])
        self.assertEqual(dynamic["properties"]["spec"]["type"], "object")
        self.assertIs(self.call("list_dynamic_report_models")[0]["spec_schema"], SPEC_SCHEMA)
        self.assertNotIn("$schema", SPEC_SCHEMA)
        self.assertEqual(SPEC_SCHEMA["type"], "object")

    def test_instructions_add_the_report_items(self):
        from erp_framework.api import erp_mcp_site
        from erp_framework.reporting.mcp import DEFAULT_INSTRUCTIONS, REPORT_INSTRUCTIONS

        self.assertEqual(erp_mcp_site.instructions, DEFAULT_INSTRUCTIONS + REPORT_INSTRUCTIONS)

    def test_report_description_falls_back_from_attribute_to_docstring_to_title(self):
        def description():
            out, err = self.call("list_reports", {"fields": ["description"]})
            return {r["report"]: r["description"] for r in out["reports"]}["client.balances"]

        with mock.patch.object(ClientTotalBalance, "__doc__", "  Balance per client.  "):
            self.assertEqual(description(), "Balance per client.")
            with mock.patch.object(ClientTotalBalance, "report_description", "What each client owes."):
                self.assertEqual(description(), "What each client owes.")
        self.assertEqual(description(), "Clients Balances")

    def test_describe_report_payload(self):
        out, err = self.call("describe_report", {"report": "client.clientsalesmonthlyseries"})
        self.assertFalse(err, out)
        schema = out.pop("params_schema")
        self.assertEqual(
            out,
            {
                "report": "client.clientsalesmonthlyseries",
                "title": "Client Sales Monthly",
                "description": "Client Sales Monthly",
                "base_model": "reporting_tests.client",
                "base_model_name": "Client",
                "report_model": "reporting_tests.simplesales",
                "report_model_name": "Sale",
                "kind": "series",
                "group_by": "client",
                "date_field": "date",
                "time_series_pattern": "monthly",
                "crosstab_field": None,
                "columns": ["slug", "name"],
            },
        )
        self.assertEqual(set(schema["properties"]), {"start_date", "end_date", "client_id", "product_id"})
        self.assertIn("default", schema["properties"]["start_date"])

    def test_describe_report_column_names(self):
        from erp_framework.reporting.mcp import column_name

        computation = type("Computation", (), {"name": "__sales__"})
        self.assertEqual(column_name("slug"), "slug")
        self.assertEqual(column_name(("name", {"verbose_name": "Name"})), "name")
        self.assertEqual(column_name(computation), "__sales__")
        self.assertEqual(column_name(type("Unnamed", (), {"name": None})), "Unnamed")

    def test_error_details(self):
        cases = [
            ({"report": "client.nope"}, "not_found", "Unknown report 'client.nope'; call list_reports for the available codes."),
            ({"report": 5}, "invalid_params", "'report' is required."),
            ({"report": ""}, "invalid_params", "'report' is required."),
            ({"report": "client.balances", "params": ["x"]}, "invalid_params", "'params' must be an object."),
        ]
        for max_rows in (True, 0, "5"):
            cases.append(
                ({"report": "client.balances", "max_rows": max_rows}, "invalid_params", "'max_rows' must be a positive integer.")
            )
        for arguments, error, detail in cases:
            with self.subTest(arguments=arguments):
                out, err = self.call("run_report", arguments)
                self.assertTrue(err, out)
                self.assertEqual((out["error"], out["detail"]), (error, detail))

    def test_foreign_key_param_hidden_by_the_admin_names_the_choice(self):
        one_client = Client.objects.filter(pk=self.client1.pk)
        with mock.patch.object(ClientAdmin, "get_queryset", lambda admin, request: one_client):
            out, err = self.call("run_report", {"report": "client.balances", "params": {"client_id": [self.client2.pk]}})
        self.assertEqual(out["detail"], "Invalid report parameters.")
        self.assertEqual(
            out["fields"],
            {
                "client_id": [
                    {"message": f"Select a valid choice. {self.client2.pk} is not one of the available choices.", "code": "invalid_choice"}
                ]
            },
        )

    def test_every_foreign_key_param_is_checked(self):
        from erp_framework.api import erp_api_site

        one_product = Product.objects.filter(pk=self.product1.pk)
        hidden_product = {"product_id": [self.product2.pk]}
        get_model_admin = erp_api_site.get_model_admin

        def no_client_admin(app_label, model_name):
            return None if model_name == "client" else get_model_admin(app_label, model_name)
        with mock.patch.object(ProductAdmin, "get_queryset", lambda admin, request: one_product):
            for params, patch in (
                (hidden_product, mock.patch.object(erp_api_site, "get_model_admin", get_model_admin)),
                ({"client_id": [self.client1.pk], **hidden_product}, mock.patch.object(erp_api_site, "get_model_admin", no_client_admin)),
            ):
                with self.subTest(params=params), patch:
                    out, err = self.call("run_report", {"report": "client.balances", "params": params})
                    self.assertTrue(err, out)
                    self.assertEqual(set(out["fields"]), {"product_id"})

    def test_run_report_names_the_report(self):
        out = self.run_report("client.balances")
        self.assertEqual((out["report"], out["title"]), ("client.balances", "Clients Balances"))

    def test_report_form_errors_keep_detail(self):
        with mock.patch.object(ClientTotalBalance, "run", side_effect=ValidationError("Dates are reversed.")):
            out, err = self.call("run_report", {"report": "client.balances"})
        self.assertEqual(out["detail"], "Invalid report parameters.")
        self.assertEqual(out["non_field_errors"], ["Dates are reversed."])

    def test_validation_error_splits_field_and_non_field_errors(self):
        from erp_framework.reporting.mcp import _validation_error

        error = _validation_error(
            ValidationError({NON_FIELD_ERRORS: ["Whole form."], "start_date": [ValidationError("Bad date.", code="invalid")]}),
            "Invalid.",
        )
        self.assertEqual(error.detail, "Invalid.")
        self.assertEqual(error.extra["fields"], {"start_date": [{"message": "Bad date.", "code": "invalid"}]})
        self.assertEqual(error.extra["non_field_errors"], ["Whole form."])
        self.assertNotIn("non_field_errors", _validation_error(ValidationError({"f": ["x"]}), "Invalid.").extra)


@unittest.skipUnless(HAS_ADMIN_API, "needs django-admin-api-mcp")
@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class RowPolicyTests(BaseTestData, TestCase):
    """run_report's row policy: declared totals, summary-first list reports, help lines and error help."""

    call = ReportToolsTests.call
    run_report = ReportToolsTests.run_report
    column_names = ReportToolsTests.column_names

    def small_site(self, token=None, **attrs):
        from erp_framework.api import ERPMcpSite, erp_api_site

        site = type("SmallSite", (ERPMcpSite,), attrs)(erp_api_site, name="small_mcp")

        def call(name, arguments):
            out, err = self.call(name, arguments, token=token, site=site)
            self.assertFalse(err, out)
            return out

        return call

    def test_default_max_rows_is_50(self):
        from erp_framework.api import erp_mcp_site

        self.assertEqual(erp_mcp_site.report_max_rows, 50)
        tools = {t.name: t for t in erp_mcp_site.get_tools()}
        self.assertEqual(tools["run_report"].input_schema["properties"]["max_rows"]["default"], 50)

    def test_declared_total_columns_are_totalled_alone(self):
        out = self.run_report("client.clientdetailedstatement")
        value = self.column_names(out).index("value")
        expected = sum(Decimal(row[value]) for row in out["rows"])
        self.assertEqual(out["totals"], {"value": format(expected, "f")})

    def test_row_limit_reaches_the_list_report_generator(self):
        from slick_reporting.generator import ListViewReportGenerator

        full = self.run_report("client.clientdetailedstatement")
        database_totals = ListViewReportGenerator.get_database_totals
        with mock.patch.object(
            ListViewReportGenerator, "get_database_totals", autospec=True, side_effect=database_totals
        ) as totals:
            out = self.run_report("client.clientdetailedstatement", max_rows=2)
        totals.assert_called_once()
        self.assertEqual(len(out["rows"]), 2)
        self.assertEqual((out["row_count"], out["totals"]), (full["row_count"], full["totals"]))

    def test_summary_first_for_a_list_report_over_the_default(self):
        call = self.small_site(report_max_rows=2, report_summary_rows=1)
        full = self.run_report("client.clientdetailedstatement")
        out = call("run_report", {"report": "client.clientdetailedstatement"})
        self.assertEqual(len(out["rows"]), 1)
        self.assertTrue(out["truncated"])
        self.assertEqual((out["row_count"], out["totals"]), (full["row_count"], full["totals"]))
        self.assertEqual(
            out["help"],
            [
                f"1 of {full['row_count']} rows shown; totals cover all {full['row_count']}.",
                "For one record pass params {'client_id': [<id>]} with an ID from resolve_entities.",
                "For totals run client.balances (Clients Balances).",
                "For more rows pass max_rows (up to 1000).",
            ],
        )
        explicit = call("run_report", {"report": "client.clientdetailedstatement", "max_rows": 3})
        self.assertEqual(len(explicit["rows"]), 3)

    def test_a_report_without_total_columns_keeps_its_rows(self):
        call = self.small_site(report_max_rows=2, report_summary_rows=1)
        out = call("run_report", {"report": "client.clientdatedstatement"})
        self.assertEqual(len(out["rows"]), 2)
        self.assertEqual(out["totals"], {})

    def test_truncated_group_report_names_top_n_and_one_record(self):
        out = self.small_site(report_max_rows=1)("run_report", {"report": "client.balances"})
        self.assertEqual(
            out["help"],
            [
                "1 of 3 rows shown; totals cover all 3.",
                "For a top N pass order_by='-__balance__' and max_rows=<n> (order_by keys: __balance__, __total__).",
                "For one record pass params {'client_id': [<id>]} with an ID from resolve_entities.",
                "For more rows pass max_rows (up to 1000).",
            ],
        )
        top = self.run_report("client.balances", order_by="-__balance__", max_rows=1)
        self.assertTrue(top["truncated"])
        self.assertNotIn("help", top)
        self.assertNotIn("help", self.run_report("client.balances"))

    def test_empty_result_says_so_and_names_the_window(self):
        out = self.run_report(
            "client.clientdatedstatement",
            {"client_id": [self.client1.pk], "start_date": "2001-01-01", "end_date": "2001-01-31"},
        )
        self.assertEqual(out["rows"], [])
        self.assertEqual(
            out["help"],
            [
                "No rows match.",
                "Widen start_date and end_date in params (now: From 2001-01-01 to 2001-01-31).",
                "Or drop the client_id filter.",
            ],
        )

    def test_empty_result_with_an_open_ended_window(self):
        def empty_help(start_date, end_date):
            params = {"client_id": [self.client1.pk], "start_date": start_date, "end_date": end_date}
            return self.run_report("client.clientdatedstatement", params)["help"]

        self.assertEqual(
            empty_help("2999-01-01", None),
            ["No rows match.", "Widen start_date and end_date in params (now: From 2999-01-01).", "Or drop the client_id filter."],
        )
        self.assertEqual(
            empty_help(None, "2001-01-31"),
            ["No rows match.", "Widen start_date and end_date in params (now: As of 2001-01-31).", "Or drop the client_id filter."],
        )

    def test_summary_report_the_user_may_not_run_is_not_named(self):
        token = type("Token", (), {"scopes": ["reporting_tests.client:view"], "prefix": "t"})()
        scoped = self.small_site(token=token, report_max_rows=2, report_summary_rows=1)
        call = self.small_site(report_max_rows=2, report_summary_rows=1)
        with mock.patch.object(ClientDetailedStatement, "summary_report", "product.total_sales"):
            out = scoped("run_report", {"report": "client.clientdetailedstatement"})
            self.assertFalse([line for line in out["help"] if "product.total_sales" in line])
            out = call("run_report", {"report": "client.clientdetailedstatement"})
        self.assertIn("For totals run product.total_sales (Product Sales).", out["help"])

    def test_unknown_report_names_the_closest_code(self):
        out, err = self.call("run_report", {"report": "client.balance"})
        self.assertTrue(err)
        self.assertEqual(out["help"], ["Closest report: run_report(report='client.balances')."])
        out, err = self.call("run_report", {"report": "zzz"})
        self.assertEqual(out["help"], ["Call list_reports for the codes you may run."])

    def test_bad_params_carry_the_fixed_call(self):
        out, err = self.call("run_report", {"report": "client.balances", "params": {"client": [1]}})
        self.assertTrue(err)
        self.assertEqual(out["help"], ["run_report(report='client.balances', params={'client_id': [1]})"])
        out, err = self.call("run_report", {"report": "client.balances", "params": {"client_id": ["x"]}})
        self.assertEqual(
            out["help"], ["run_report(report='client.balances', params={'client_id': ['<id from resolve_entities>']})"]
        )
        out, err = self.call("run_report", {"report": "client.balances", "order_by": "-balance"})
        self.assertEqual(out["help"], ["run_report(report='client.balances', order_by='-__balance__')"])

    def test_list_reports_defaults_to_four_fields(self):
        out, err = self.call("list_reports")
        self.assertFalse(err, out)
        self.assertEqual(
            {r["report"]: r for r in out["reports"]}["client.balances"],
            {
                "report": "client.balances",
                "question": "Clients Balances",
                "params": {"client_id": "reporting_tests.client", "product_id": "reporting_tests.product"},
                "order_by": {"__balance__": "Closing Total", "__total__": "Sum of value"},
            },
        )
        out, err = self.call("list_reports", {"fields": ["kind"]})
        self.assertEqual({r["report"]: r for r in out["reports"]}["client.balances"]["kind"], "group")
        out, err = self.call("list_reports", {"fields": ["nope"]})
        self.assertTrue(err)
        self.assertEqual(out["error"], "invalid_params")
        self.assertIn("'fields' takes any of: title, description", out["help"][0])

    def test_row_policy_defaults(self):
        from erp_framework.api import erp_mcp_site

        self.assertEqual((erp_mcp_site.report_max_rows, erp_mcp_site.report_summary_rows), (50, 10))

    def test_unknown_list_field_names_the_choices(self):
        from erp_framework.api import erp_mcp_site
        from erp_framework.reporting.mcp import DEFAULT_ENTRY_FIELDS, ENTRY_FIELDS

        extra = [name for name in ENTRY_FIELDS if name not in DEFAULT_ENTRY_FIELDS]
        schema = {t.name: t.input_schema for t in erp_mcp_site.get_tools()}["list_reports"]
        self.assertEqual(schema["properties"]["fields"]["items"], {"enum": extra})
        out, err = self.call("list_reports", {"fields": ["nope"]})
        self.assertEqual(out["detail"], "Unknown fields ['nope'].")
        self.assertEqual(out["help"], [f"'fields' takes any of: {', '.join(extra)}."])

    def test_unmatched_param_lists_the_report_params(self):
        out, err = self.call("run_report", {"report": "client.balances", "params": {"zzzzzz": [1]}})
        self.assertTrue(err)
        self.assertEqual(out["help"], ["Parameters of this report: client_id, product_id."])

    def test_empty_result_names_every_filter(self):
        out = self.run_report(
            "client.clientdetailedstatement", {"client_id": [self.clientIdle.pk], "product_id": [self.product1.pk]}
        )
        self.assertEqual(out["help"], ["No rows match.", "Or drop the client_id, product_id filter."])

    def test_truncated_help_follows_the_base_model_params_and_cap(self):
        out = self.small_site(report_max_rows=1)("run_report", {"report": "product.productclientsalesmatrix"})
        self.assertIn("For one record pass params {'product_id': [<id>]} with an ID from resolve_entities.", out["help"])
        clients = [self.client1.pk, self.client2.pk]
        out = self.small_site(report_max_rows=1)("run_report", {"report": "client.balances", "params": {"client_id": clients}})
        self.assertFalse([line for line in out["help"] if line.startswith("For one record")])
        out = self.small_site(report_max_rows=2, report_max_rows_cap=2)("run_report", {"report": "client.balances"})
        self.assertFalse([line for line in out["help"] if line.startswith("For more rows")])

    def test_summary_report_as_a_class_and_never_itself(self):
        call = self.small_site(report_max_rows=2, report_summary_rows=1)
        with mock.patch.object(ClientDetailedStatement, "summary_report", ClientTotalBalance):
            out = call("run_report", {"report": "client.clientdetailedstatement"})
        self.assertIn("For totals run client.balances (Clients Balances).", out["help"])
        with mock.patch.object(ClientDetailedStatement, "summary_report", "client.clientdetailedstatement"):
            out = call("run_report", {"report": "client.clientdetailedstatement"})
        self.assertFalse([line for line in out["help"] if line.startswith("For totals")])

    def test_explicit_max_rows_over_the_cap_names_the_row_count_and_top_n(self):
        out = self.small_site(report_max_rows_cap=2)("run_report", {"report": "client.balances", "max_rows": 200})
        self.assertEqual(
            out["help"],
            [
                "2 of 3 rows shown; totals cover all 3.",
                "For a top N pass order_by='-__balance__' and max_rows=<n> (order_by keys: __balance__, __total__).",
                "For one record pass params {'client_id': [<id>]} with an ID from resolve_entities.",
            ],
        )
        call = self.small_site(report_max_rows=1)
        out = call("run_report", {"report": "client.balances", "order_by": "-__balance__"})
        self.assertEqual(out["help"][0], "1 of 3 rows shown; totals cover all 3.")
        self.assertFalse([line for line in out["help"] if line.startswith("For a top N")])

    def test_row_count_line_without_totals(self):
        out = self.small_site(report_max_rows=2)("run_report", {"report": "client.clientdatedstatement"})
        self.assertEqual(
            out["help"],
            [
                f"2 of {out['row_count']} rows shown.",
                "For one record pass params {'client_id': [<id>]} with an ID from resolve_entities.",
                "For a top N or totals per group run_dynamic_report on reporting_tests.SimpleSales with kind "
                "'aggregate', group_by, order_by and max_rows=<n>.",
                "For more rows pass max_rows (up to 1000).",
            ],
        )

    def test_truncated_dynamic_report_names_the_row_count_and_top_n(self):
        call = self.small_site(report_max_rows=1)
        out = call("run_dynamic_report", {"spec": SALES_BY_CLIENT})
        shown = f"1 of {out['row_count']} rows shown; totals cover all {out['row_count']}."
        more = "For more rows pass max_rows (up to 1000)."
        self.assertEqual(out["help"], [shown, "For a top N pass order_by='-sales' and max_rows=<n>.", more])
        out = call("run_dynamic_report", {"spec": SALES_BY_CLIENT, "order_by": "-sales"})
        self.assertEqual(out["help"], [shown, more])
        out = call("run_dynamic_report", {"spec": SALES_BY_CLIENT, "max_rows": 1})
        self.assertEqual(out["help"], [shown, "For a top N pass order_by='-sales' and max_rows=<n>."])
        top = call("run_dynamic_report", {"spec": SALES_BY_CLIENT, "order_by": "-sales", "max_rows": 1})
        self.assertNotIn("help", top)
        names = call("run_dynamic_report", {"spec": {**SALES_BY_CLIENT, "columns": ["name"]}, "max_rows": 1})
        self.assertEqual(names["help"], [f"1 of {names['row_count']} rows shown."])
        self.assertNotIn("help", self.small_site()("run_dynamic_report", {"spec": SALES_BY_CLIENT}))

    def test_truncated_dynamic_list_points_to_an_aggregate(self):
        call = self.small_site()
        spec = {"report_model": "reporting_tests.SimpleSales", "kind": "list", "columns": ["slug", "value"]}
        out = call("run_dynamic_report", {"spec": spec, "max_rows": 2})
        self.assertEqual(
            out["help"][1:],
            [
                "For a top N or totals per group use kind 'aggregate' with group_by and the column "
                "{'method': 'Sum', 'field': 'value', 'name': 'value'}, then order_by='-value' and max_rows=<n>."
            ],
        )
        out = call("run_dynamic_report", {"spec": {**spec, "columns": ["slug"]}, "max_rows": 2})
        self.assertIn("'field': '<number field>'", out["help"][1])

    def test_top_n_routing_within_the_description_budget(self):
        from erp_framework.reporting import mcp

        self.assertIn("For a top N or 'which X' question, run a report grouped by X with order_by", mcp.REPORT_INSTRUCTIONS)
        self.assertLessEqual(len(mcp.RUN_REPORT_DESCRIPTION), 642)
        self.assertLessEqual(len(mcp.RUN_DYNAMIC_REPORT_DESCRIPTION), 1160)


@unittest.skipUnless(HAS_ADMIN_API, "needs django-admin-api-mcp")
@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class ReportRoutingTests(BaseTestData, TestCase):
    call = ReportToolsTests.call

    def test_hidden_base_model_hides_its_reports_and_params(self):
        with mock.patch.object(ProductAdmin, "mcp_enabled", False, create=True):
            out, err = self.call("list_reports")
            self.assertFalse(err, out)
            reports = {r["report"]: r for r in out["reports"]}
            self.assertTrue(reports)
            self.assertFalse([code for code in reports if code.startswith("product.")])
            self.assertEqual(reports["client.balances"]["params"], {"client_id": "reporting_tests.client"})
            out, err = self.call("describe_report", {"report": "client.balances"})
            self.assertFalse(err, out)
            self.assertNotIn("product_id", out["params_schema"]["properties"])
            self.assertIn("client_id", out["params_schema"]["properties"])
            out, err = self.call("run_report", {"report": "product.productsalesmonthlyseries"})
        self.assertTrue(err)
        self.assertEqual(out["error"], "not_found")

    def run_report_description(self, site=None, user=None):
        from erp_framework.api import erp_mcp_site

        request = RequestFactory().post("/mcp/")
        request.user = user or self.user
        return next(t for t in (site or erp_mcp_site).get_tools(request) if t.name == "run_report").description

    def catalog(self, description):
        """The catalog lines in a run_report description, or None without a catalog."""
        _, _, catalog = description.partition("\n\nReports you may run")
        return catalog.splitlines()[1:] if catalog else None

    def test_run_report_description_lists_the_users_reports(self):
        from erp_framework.api import erp_mcp_site
        from erp_framework.reporting.mcp import RUN_REPORT_DESCRIPTION

        description = self.run_report_description()
        self.assertTrue(
            description.startswith(RUN_REPORT_DESCRIPTION + "\n\nReports you may run, dates all (code: question|shape|")
        )
        self.assertLessEqual(len(description), 4096)
        self.assertIn("run one directly; describe_report only adds columns", description)
        self.assertIn("A top N or 'which X' is the report by X with order_by and max_rows N.", description)
        self.assertIn("Everything but 'report' is optional", description)
        self.assertIn("(omitted: the report's own order)", description)
        lines = self.catalog(description)
        self.assertEqual(len(lines), len(self.call("list_reports")[0]["reports"]))
        self.assertIn(
            "client.balances: Clients Balances|by client|client_id, product_id|"
            "order_by __balance__=Closing Total, __total__=Sum of value|balance",
            lines,
        )
        self.assertIn(
            f"client.clientdatedstatement: Client dated statement|list|client_id, product_id|dates {year}-01-01 to today",
            lines,
        )
        request = RequestFactory().post("/mcp/")
        request.user = self.user
        self.assertEqual(erp_mcp_site.get_instructions(request), erp_mcp_site.instructions)
        self.assertNotIn("Reports you may run", erp_mcp_site.instructions)

    def test_short_question_is_report_question_else_title(self):
        with mock.patch.object(ClientTotalBalance, "report_question", "Who owes us money?", create=True):
            reports = {r["report"]: r for r in self.call("list_reports")[0]["reports"]}
        self.assertEqual(reports["client.balances"]["question"], "Who owes us money?")
        self.assertEqual(reports["client.clientdetailedstatement"]["question"], "Client statement")

    def test_report_shape_and_default_dates_edges(self):
        import datetime

        from erp_framework.reporting.mcp import default_dates, report_shape

        from .reports import ClientSalesMonthlySeries

        request = RequestFactory().post("/mcp/")
        request.user = self.user
        with mock.patch.object(ClientTotalBalance, "time_series_selector", True):
            self.assertEqual(report_shape(ClientTotalBalance), "by client series")
        with mock.patch.object(ClientTotalBalance, "group_by", None):
            self.assertEqual(report_shape(ClientTotalBalance), "group")
        with mock.patch.multiple(ClientTotalBalance, start_date_field_name="date", end_date_field_name="date"):
            self.assertEqual(default_dates(request, ClientTotalBalance), f"{year}-01-01 to today")
        own = {"start_date": datetime.date(2025, 1, 1), "end_date": None}
        with mock.patch.object(ClientSalesMonthlySeries, "get_initial", lambda view: own):
            self.assertEqual(default_dates(request, ClientSalesMonthlySeries), "2025-01-01 to any")

    def test_catalog_drops_detail_to_fit(self):
        from erp_framework.api import erp_mcp_site

        budget = len(self.run_report_description()) - 1
        with mock.patch.object(ClientTotalBalance, "report_question", "Who owes us money?", create=True):
            for header, line in (
                (
                    "Reports you may run, dates all (code: question|shape|params|order_by keys):",
                    "client.balances: Who owes us money?|by client|client_id, product_id|order_by __balance__, __total__",
                ),
                (
                    "Reports you may run, dates all (code|shape|params|order_by keys;",
                    "client.balances|by client|client_id, product_id|order_by __balance__, __total__",
                ),
                ("Reports you may run (codes;", "client.balances"),
            ):
                with mock.patch.object(type(erp_mcp_site), "report_tool_description_max_chars", budget):
                    description = self.run_report_description()
                self.assertIn("\n\n" + header, description)
                self.assertLessEqual(len(description), budget)
                self.assertIn(line, self.catalog(description))
                budget = len(description) - 1

    def test_realistic_report_set_keeps_its_questions(self):
        from erp_framework.api import erp_mcp_site

        # 27 reports sized like a downstream services ERP's catalog (codes up to 50 chars, up to 3 params)
        bases = ("client", "treasury", "expense", "service", "servicecategory")
        entries = [
            {
                "report": f"{base}.{base}-{('total', 'sales-monthly', 'detailed-statement')[n % 3]}",
                "description": "Which clients bought the most services in the period, net of credit notes?",
                "question": "How much did each client buy per month?",
                "shape": ("list", f"by {base} monthly", f"by {base}")[n % 3],
                "params": dict.fromkeys(("treasury_id", "expense_id", "liability_id") if n % 4 == 0 else ("treasury_id",)),
                "order_by": dict.fromkeys(("total_value", "__balance__") if n % 2 else ()),
                "balance": True,
                "dates": "1900-01-01 to today" if n == 7 else "2026-01-01 to today",
            }
            for n in range(27)
            for base in [bases[n % 5]]
        ]
        reports = [ClientTotalBalance] * 27
        with mock.patch.object(type(erp_mcp_site), "get_reports", lambda site, request, code=None: reports), \
                mock.patch("erp_framework.reporting.mcp.report_entry", side_effect=entries):
            description = self.run_report_description()
        self.assertLessEqual(len(description), 4096)
        self.assertIn(
            "\n\nReports you may run, dates 2026-01-01 to today (code: question|shape|params|order_by keys):",
            description,
        )
        lines = self.catalog(description)
        self.assertEqual(len(lines), 27)
        self.assertEqual(
            lines[0],
            "client.client-total: How much did each client buy per month?|list|treasury_id, expense_id, liability_id",
        )
        self.assertEqual(
            lines[7],
            "expense.expense-sales-monthly: How much did each client buy per month?|by expense monthly|treasury_id"
            "|order_by total_value, __balance__|dates 1900-01-01 to today",
        )

    def test_catalog_lists_only_reports_the_user_may_run(self):
        UserReportPermission.objects.create(
            user=self.limited_user, report_code=ClientTotalBalance.get_report_code(), view=True
        )
        lines = self.catalog(self.run_report_description(user=self.limited_user))
        self.assertEqual(
            lines,
            [
                "client.balances: Clients Balances|by client|client_id, product_id|"
                "order_by __balance__=Closing Total, __total__=Sum of value|balance"
            ],
        )

    def test_catalog_is_left_out_when_it_does_not_fit_or_without_a_user(self):
        from django.contrib.auth.models import AnonymousUser

        from erp_framework.api import erp_mcp_site
        from erp_framework.reporting.mcp import RUN_REPORT_DESCRIPTION

        reports = self.call("list_reports")[0]["reports"]
        with mock.patch.object(type(erp_mcp_site), "report_catalog_max", len(reports) - 1):
            self.assertEqual(self.run_report_description(), RUN_REPORT_DESCRIPTION)
        budget = len(RUN_REPORT_DESCRIPTION) + 50
        with mock.patch.object(type(erp_mcp_site), "report_tool_description_max_chars", budget):
            self.assertEqual(self.run_report_description(), RUN_REPORT_DESCRIPTION)
        self.assertEqual(self.run_report_description(user=AnonymousUser()), RUN_REPORT_DESCRIPTION)
        tools = {tool.name: tool for tool in erp_mcp_site.get_tools()}
        self.assertEqual(tools["run_report"].description, RUN_REPORT_DESCRIPTION)

    def test_catalog_kept_at_exact_fit_and_report_limit(self):
        from erp_framework.api import erp_mcp_site

        self.assertEqual((erp_mcp_site.report_catalog_max, erp_mcp_site.report_tool_description_max_chars), (40, 4096))
        description = self.run_report_description()
        reports = self.call("list_reports")[0]["reports"]
        with mock.patch.object(type(erp_mcp_site), "report_tool_description_max_chars", len(description)), \
                mock.patch.object(type(erp_mcp_site), "report_catalog_max", len(reports)):
            self.assertEqual(self.run_report_description(), description)

    def test_catalog_needs_a_request_user(self):
        from erp_framework.api import erp_mcp_site
        from erp_framework.reporting.mcp import RUN_REPORT_DESCRIPTION

        tools = {tool.name: tool for tool in erp_mcp_site.get_tools(RequestFactory().post("/mcp/"))}
        self.assertEqual(tools["run_report"].description, RUN_REPORT_DESCRIPTION)

    def test_order_by_error_shape(self):
        out, err = self.call("run_report", {"report": "client.balances", "order_by": "-name"})
        self.assertEqual(out["detail"], "Invalid report parameters.")
        self.assertEqual(
            out["fields"],
            {"order_by": [{"message": "Sort by one of: __balance__, __total__; prefix '-' for highest first.", "code": "invalid"}]},
        )

    def test_required_params_follow_the_shown_params(self):
        from erp_framework.reporting import mcp

        form_object_schema = mcp.form_object_schema

        def all_required(form_class, **kwargs):
            return {**form_object_schema(form_class, **kwargs), "required": ["client_id", "product_id"]}

        def required():
            out, err = self.call("describe_report", {"report": "client.balances"})
            self.assertFalse(err, out)
            return out["params_schema"]["required"]

        self.assertEqual(required(), [])
        with mock.patch.object(mcp, "form_object_schema", all_required):
            self.assertEqual(required(), ["client_id", "product_id"])
            with mock.patch.object(ProductAdmin, "mcp_enabled", False, create=True):
                self.assertEqual(required(), ["client_id"])

    def test_balance_and_labels_read_every_column_shape(self):
        from erp_framework.reporting.mcp import column_labels, computation_classes, is_balance_report

        columns = {"columns": [("slug", {}), ("__balance__", {"verbose_name": "Balance"})], "time_series_columns": None}
        self.assertTrue(is_balance_report(type("TupleColumns", (ClientTotalBalance,), columns)))
        self.assertEqual(list(computation_classes(int)), [])
        custom_groups = type(
            "CustomGroups",
            (ClientTotalBalance,),
            {"group_by": None, "group_by_custom_querysets": [SimpleSales.objects.all()], "columns": ["__total__"]},
        )
        self.assertEqual(column_labels(custom_groups), ["Sum of value"])


SALES_BY_CLIENT = {
    "report_model": "reporting_tests.SimpleSales",
    "group_by": "client",
    "columns": ["name", {"method": "Sum", "field": "value", "name": "sales"}],
}


# The key fact comes last, over two lines: the catalog keeps the whole description on one line.
SALES_DESCRIPTION = "A sale to a client.\n    Credit notes are sales too: totals over sales include them."


@unittest.skipUnless(HAS_ADMIN_API, "needs django-admin-api-mcp")
@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class DynamicReportToolTests(BaseTestData, TestCase):
    call = ReportToolsTests.call

    def grant(self, *codenames):
        self.limited_user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        self.limited_user = type(self.limited_user).objects.get(pk=self.limited_user.pk)  # drop the perm cache

    def test_group_by_with_aggregation_and_totals(self):
        out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT})
        self.assertFalse(err, out)
        self.assertEqual([c["name"] for c in out["columns"]], ["name", "sales"])
        sales = {row[0]: row[1] for row in out["rows"]}
        self.assertEqual(sales["Client 1"], "300")
        self.assertEqual(out["totals"], {"sales": format(sum(Decimal(v) for v in sales.values() if v), "f")})

    def test_time_series_and_date_range(self):
        spec = {
            **SALES_BY_CLIENT,
            "columns": ["name"],
            "date_field": "date",
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-02-28",
            "time_series_pattern": "monthly",
            "time_series_columns": [{"method": "Sum", "field": "value", "name": "sales"}],
            "filters": {"client_id__in": [self.client1.pk]},
        }
        out, err = self.call("run_dynamic_report", {"spec": spec})
        self.assertFalse(err, out)
        self.assertEqual(out["row_count"], 1)
        self.assertEqual(out["rows"][0][1:], ["100", "100"])

    def test_list_kind_with_max_rows(self):
        spec = {"report_model": "reporting_tests.SimpleSales", "kind": "list", "columns": ["date", "value"]}
        out, err = self.call("run_dynamic_report", {"spec": spec, "max_rows": 2})
        self.assertFalse(err, out)
        self.assertEqual(len(out["rows"]), 2)
        self.assertTrue(out["truncated"])

    def test_order_by_with_max_rows_gives_a_top_n(self):
        everything, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT})
        rows = sorted(everything["rows"], key=lambda row: Decimal(row[1]))
        for order_by, expected in (("-sales", rows[::-1][:2]), ("sales", rows[:2])):
            with self.subTest(order_by=order_by):
                out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT, "order_by": order_by, "max_rows": 2})
                self.assertFalse(err, out)
                self.assertEqual(out["rows"], expected)
                self.assertEqual((out["totals"], out["truncated"]), (everything["totals"], True))

    def test_order_by_puts_empty_cells_last(self):
        from erp_framework.api import erp_mcp_site

        spec = {"report_model": "reporting_tests.SimpleSales", "kind": "list", "columns": ["slug", "value"]}
        hidden = {"name": "pk", "verbose_name": "pk", "type": "number", "visible": False}
        empty_first = {
            "columns": [{"name": "slug", "verbose_name": "slug", "type": "text"}, hidden],
            "data": {"slug": [None, "", "b", "a", "c"], "pk": [1, 2, 3, 4, 5]},
        }
        with mock.patch("erp_framework.reporting.mcp.run_dynamic_report", return_value=empty_first):
            for order_by, expected in (("slug", ["a", "b", "c", None, None]), ("-slug", ["c", "b", "a", None, None])):
                with self.subTest(order_by=order_by):
                    out, err = self.call("run_dynamic_report", {"spec": spec, "order_by": order_by})
                    self.assertEqual([row[0] for row in out["rows"]], expected)
            out, err = self.call("run_dynamic_report", {"spec": spec, "order_by": "pk"})
            self.assertEqual(out["fields"]["order_by"][0]["message"], "Sort by one of: slug; prefix '-' for highest first.")
        out, err = self.call("run_dynamic_report", {"spec": spec, "order_by": "-value"})
        self.assertEqual([Decimal(row[1]) for row in out["rows"]], sorted(SimpleSales.objects.values_list("value", flat=True), reverse=True))
        for order_by in ("-nope", 5):
            with self.subTest(order_by=order_by):
                out, err = self.call("run_dynamic_report", {"spec": spec, "order_by": order_by})
                self.assertEqual(out["fields"]["order_by"][0]["message"], "Sort by one of: slug, value; prefix '-' for highest first.")
        tools = {t.name: t for t in erp_mcp_site.get_tools()}
        order_by = {"type": "string", "description": "A column name of the result, e.g. '-sales' for highest first."}
        self.assertEqual(tools["run_dynamic_report"].input_schema["properties"]["order_by"], order_by)

    def test_unknown_field_error_carries_the_corrected_spec(self):
        series = {**SALES_BY_CLIENT, "date_field": "date", "start_date": f"{year}-01-01", "end_date": f"{year}-02-28", "time_series_pattern": "monthly"}
        sales = SALES_BY_CLIENT["columns"][1]
        value = {"method": "Sum", "field": "value", "name": "value"}
        crosstab = {**SALES_BY_CLIENT, "crosstab_field": "product", "crosstab_ids": [self.product1.pk]}
        for spec, key, given, fixed in (
            (series, "time_series_columns", ["sales", "value", "__total__"], [sales, value, "__total__"]),
            (crosstab, "crosstab_columns", ["value", sales], [value, sales]),
        ):
            with self.subTest(key=key, given=given):
                out, err = self.call("run_dynamic_report", {"spec": {**spec, key: given}})
                self.assertEqual(out["fields"][key][0]["code"], "unknown_field")
                corrected = {**spec, key: fixed}
                self.assertEqual(out["help"], [f"run_dynamic_report(spec={json.dumps(corrected)})"])
                self.assertFalse(self.call("run_dynamic_report", {"spec": corrected})[1])
        out, err = self.call("run_dynamic_report", {"spec": {**SALES_BY_CLIENT, "group_by": "nope", "crosstab_columns": "sales"}})
        self.assertEqual(out["help"], ["list_dynamic_report_models gives the fields of each kind of record."])
        out, err = self.call("run_dynamic_report", {"spec": {**SALES_BY_CLIENT, "kind": 5}})
        self.assertNotIn("help", out)

    def test_bad_spec_is_invalid_params(self):
        spec = {**SALES_BY_CLIENT, "columns": [{"method": "Sum", "field": "no_such_field"}]}
        out, err = self.call("run_dynamic_report", {"spec": spec})
        self.assertTrue(err)
        self.assertEqual(out["error"], "invalid_params")
        self.assertIn("columns", out["fields"])

    def test_spec_grammar_comes_with_the_models(self):
        from erp_framework.api import erp_mcp_site

        tools = {t.name: t for t in erp_mcp_site.get_tools()}
        self.assertEqual(tools["run_dynamic_report"].input_schema["properties"]["spec"]["type"], "object")
        self.assertNotIn("properties", tools["run_dynamic_report"].input_schema["properties"]["spec"])
        out, err = self.call("list_dynamic_report_models")
        self.assertFalse(err, out)
        self.assertEqual(out["spec_schema"]["required"], ["report_model"])
        self.assertIn("group_by", out["spec_example"])

    def dynamic_description(self, user=None, **site_attrs):
        from erp_framework.api import ERPMcpSite, erp_api_site

        request = RequestFactory().post("/mcp/")
        request.user = user or self.user
        site = type("SmallSite", (ERPMcpSite,), site_attrs)(erp_api_site, name="small_mcp")
        return {tool.name: tool for tool in site.get_tools(request)}["run_dynamic_report"].description

    def test_dynamic_spec_and_catalog_in_the_tool_description(self):
        from erp_framework.reporting.mcp import DYNAMIC_CATALOG_HEADERS, RUN_DYNAMIC_REPORT_DESCRIPTION, SPEC_GUIDE

        description = self.dynamic_description()
        self.assertTrue(description.startswith(RUN_DYNAMIC_REPORT_DESCRIPTION + "\n\n" + DYNAMIC_CATALOG_HEADERS["fields"]))
        self.assertIn(SPEC_GUIDE, description)
        self.assertIn(
            "Returns the same shape as run_report; with group_by, each row starts with its group's label. order_by "
            "takes a column name, '-name' for highest first. A top N or 'which X' is an aggregate by X with order_by "
            "and max_rows N, not a list. Spec: kind 'aggregate'",
            description,
        )
        self.assertIn(
            "crosstab_field with crosstab_columns (both lists of {method, field, name}), filters "
            "{'<field path>__<lookup>': value}. Example: {",
            description,
        )
        self.assertIn('"time_series_pattern": "monthly", "time_series_columns": [{"method": "Sum", "field": "value", "name": "sales"}]}', description)
        self.assertIn('Example: {"report_model": "store.SalesLine", "group_by": "client"', description)
        self.assertIn("method one of Avg, Count, Max, Min, Sum", description)
        self.assertIn("(annually, bi-weekly, daily, monthly, quarterly, semiannually, weekly)", description)
        sales = "\nreporting_tests.SimpleSales (Sale): id#, slug, date@, value#, quantity#, price#, client>reporting_tests.Client, product>reporting_tests.Product"
        self.assertIn(sales, description)
        self.assertLessEqual(len(description), 4096)
        with mock.patch.object(SimpleSalesAdmin, "get_exclude", lambda admin, request, obj=None: ("value", "client")):
            hidden = self.dynamic_description()
        self.assertIn("reporting_tests.SimpleSales (Sale): id#, slug, date@, quantity#, price#, product>reporting_tests.Product", hidden.splitlines())

    def test_dynamic_catalog_carries_each_model_description(self):
        with mock.patch.object(SimpleSalesAdmin, "mcp_description", SALES_DESCRIPTION, create=True):
            description = self.dynamic_description()
            models = {entry["identifier"]: entry for entry in self.call("list_dynamic_report_models")[0]["models"]}
        self.assertIn(
            "reporting_tests.SimpleSales (Sale): id#, slug, date@, value#, quantity#, price#, client>reporting_tests.Client, "
            "product>reporting_tests.Product|A sale to a client. Credit notes are sales too: totals over sales include them.",
            description.splitlines(),
        )
        self.assertIn("\nreporting_tests.Client: id#, slug, name, notes\n", description)
        self.assertEqual(models["reporting_tests.SimpleSales"]["description"], SALES_DESCRIPTION)
        self.assertNotIn("description", models["reporting_tests.Client"])

    def test_dynamic_catalog_drops_detail_to_fit(self):
        from django.contrib.auth.models import AnonymousUser

        from erp_framework.reporting.mcp import DYNAMIC_CATALOG_HEADERS, RUN_DYNAMIC_REPORT_DESCRIPTION

        sales = " ".join(SALES_DESCRIPTION.split())
        with mock.patch.object(SimpleSalesAdmin, "mcp_description", SALES_DESCRIPTION, create=True):
            full = self.dynamic_description()
            self.assertEqual(self.dynamic_description(report_tool_description_max_chars=len(full)), full)
            reportable = self.dynamic_description(report_tool_description_max_chars=len(full) - 1)
            models = self.dynamic_description(report_tool_description_max_chars=len(reportable) - 1)
            names = self.dynamic_description(report_tool_description_max_chars=len(models) - 1)
            fallback = self.dynamic_description(report_tool_description_max_chars=len(names) - 1)
        lines = reportable.splitlines()
        self.assertIn(DYNAMIC_CATALOG_HEADERS["reportable"], lines)
        self.assertIn("reporting_tests.Client: id#", lines)
        self.assertIn("reporting_tests.Journal: id#, date@, value#", lines)
        self.assertIn(
            "reporting_tests.SimpleSales (Sale): id#, date@, value#, quantity#, price#, client>reporting_tests.Client, "
            f"product>reporting_tests.Product|{sales}",
            lines,
        )
        lines = models.splitlines()
        self.assertIn(DYNAMIC_CATALOG_HEADERS["models"], lines)
        self.assertIn("reporting_tests.Client", lines)
        self.assertIn(f"reporting_tests.SimpleSales (Sale)|{sales}", lines)
        lines = names.splitlines()
        self.assertIn(DYNAMIC_CATALOG_HEADERS["names"], lines)
        self.assertIn("reporting_tests.SimpleSales (Sale)", lines)
        self.assertNotIn("Credit notes", names)
        self.assertEqual(fallback, RUN_DYNAMIC_REPORT_DESCRIPTION + " list_dynamic_report_models gives the kinds of record.")
        self.assertEqual(self.dynamic_description(user=AnonymousUser()), fallback)
        self.assertEqual(self.dynamic_description(user=self.limited_user), fallback)
        from erp_framework.api import erp_mcp_site

        self.assertEqual({t.name: t for t in erp_mcp_site.get_tools()}["run_dynamic_report"].description, fallback)

    def test_tool_lookup_skips_the_catalogs(self):
        from erp_framework.api import erp_mcp_site

        request = RequestFactory().post("/mcp/")
        request.user = self.user
        site = type(erp_mcp_site)
        with mock.patch.object(site, "get_report_catalog") as reports, mock.patch.object(site, "get_dynamic_report_catalog") as dynamic:
            self.assertEqual(erp_mcp_site.get_tool("run_dynamic_report", request).name, "run_dynamic_report")
            self.assertEqual(erp_mcp_site.get_tool("list_models", request).name, "list_models")
            self.assertIsNone(erp_mcp_site.get_tool("no_such_tool", request))
            self.assertFalse(self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT})[1])
        self.assertEqual({c.args[0] for c in [*reports.call_args_list, *dynamic.call_args_list]}, {None})

    def test_model_without_reportable_fields_is_named_alone(self):
        from erp_framework.reporting.mcp import dynamic_catalog_line

        entry = {"identifier": "a.BeeHive", "verbose_name": "Bee hive", "fields": [{"name": "note", "is_numeric": False, "is_date": False, "is_relation": False}]}
        self.assertEqual(dynamic_catalog_line(entry, "reportable"), "a.BeeHive")
        self.assertEqual(dynamic_catalog_line(entry, "fields"), "a.BeeHive: note")
        self.assertEqual(dynamic_catalog_line({**entry, "verbose_name": "hive"}, "names"), "a.BeeHive (hive)")

    def test_malformed_spec_types_are_invalid_params(self):
        for spec in (
            {**SALES_BY_CLIENT, "columns": "name"},
            {**SALES_BY_CLIENT, "kind": 5},
            {**SALES_BY_CLIENT, "filters": ["client_id"]},
            {"report_model": 7},
        ):
            out, err = self.call("run_dynamic_report", {"spec": spec})
            self.assertTrue(err, spec)
            self.assertEqual(out["error"], "invalid_params", (spec, out))

    def test_model_outside_the_mcp_site_is_rejected(self):
        spec = {"report_model": "reporting_tests.JournalItem", "kind": "list", "columns": ["data"]}
        out, err = self.call("run_dynamic_report", {"spec": spec})
        self.assertTrue(err)
        self.assertEqual(out["error"], "invalid_params")

    def test_user_without_model_permissions_is_denied(self):
        out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT}, user=self.limited_user)
        self.assertTrue(err)
        self.assertEqual(out["error"], "permission_denied")

    def test_group_by_model_needs_view_permission(self):
        self.grant("view_simplesales")
        out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT}, user=self.limited_user)
        self.assertTrue(err)
        self.assertEqual(out["fields"]["group_by"][0]["code"], "model_not_allowed")
        self.grant("view_client")
        out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT}, user=self.limited_user)
        self.assertFalse(err, out)

    def test_list_dynamic_report_models_follows_permissions(self):
        self.grant("view_simplesales")
        out, err = self.call("list_dynamic_report_models", user=self.limited_user)
        self.assertFalse(err, out)
        models = {m["identifier"]: m for m in out["models"]}
        self.assertEqual(set(models), {"reporting_tests.SimpleSales"})
        relations = {f["name"] for f in models["reporting_tests.SimpleSales"]["fields"] if f["is_relation"]}
        self.assertNotIn("client", relations)

    def test_token_scope_narrows_dynamic_report_models(self):
        out, err = self.call("list_dynamic_report_models", token=PRODUCT_TOKEN)
        self.assertFalse(err, out)
        self.assertEqual({m["identifier"] for m in out["models"]}, {"reporting_tests.Product"})
        out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT}, token=PRODUCT_TOKEN)
        self.assertTrue(err)
        self.assertEqual(out["fields"]["report_model"][0]["code"], "model_not_allowed")

    def test_user_model_is_not_readable(self):
        for spec in (
            {"report_model": "auth.User", "kind": "list", "columns": ["username", "password"]},
            {"report_model": "reporting_tests.SimpleSales", "kind": "list", "columns": ["lastmod_user__password"]},
            {
                "report_model": "reporting_tests.SimpleSales",
                "kind": "list",
                "columns": ["slug"],
                "filters": {"lastmod_user__password__startswith": "md5"},
            },
        ):
            out, err = self.call("run_dynamic_report", {"spec": spec})
            self.assertTrue(err, out)
            self.assertEqual(out["error"], "invalid_params")

    def test_excluded_models_are_not_readable(self):
        from erp_framework.api import ERPMcpSite, erp_api_site

        site = ERPMcpSite(
            erp_api_site,
            name="no_product_mcp",
            excluded_models=(*ERPMcpSite.excluded_models, "reporting_tests.product"),
        )
        out, err = self.call("list_dynamic_report_models", site=site)
        self.assertFalse(err, out)
        identifiers = {m["identifier"] for m in out["models"]}
        self.assertIn("reporting_tests.SimpleSales", identifiers)
        self.assertNotIn("reporting_tests.Product", identifiers)

        for key, spec in (
            ("report_model", {"report_model": "reporting_tests.Product", "kind": "list", "columns": ["name"]}),
            ("group_by", {**SALES_BY_CLIENT, "group_by": "product"}),
        ):
            with self.subTest(key=key):
                out, err = self.call("run_dynamic_report", {"spec": spec}, site=site)
                self.assertTrue(err, out)
                self.assertEqual(out["fields"][key][0]["code"], "model_not_allowed")

    def test_rows_follow_the_admin_queryset(self):
        two_clients = SimpleSales.objects.filter(client__in=[self.client1, self.client2])
        with mock.patch.object(SimpleSalesAdmin, "get_queryset", lambda admin, request: two_clients):
            out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT})
        self.assertFalse(err, out)
        self.assertEqual({row[0]: row[1] for row in out["rows"]}, {"Client 1": "300", "Client 2": "600"})
        self.assertEqual(out["totals"], {"sales": "900"})

        one_client = Client.objects.filter(pk=self.client1.pk)
        two_ids = {"client_id__in": [self.client1.pk, self.client2.pk]}
        with mock.patch.object(ClientAdmin, "get_queryset", lambda admin, request: one_client):
            for spec in (SALES_BY_CLIENT, {**SALES_BY_CLIENT, "filters": two_ids}):
                with self.subTest(spec=spec):
                    out, err = self.call("run_dynamic_report", {"spec": spec})
                    self.assertFalse(err, out)
                    self.assertEqual(out["rows"], [["Client 1", "300"]])

    def test_fields_hidden_by_the_admin_are_rejected(self):
        hidden = ("type", "client", "value")
        with mock.patch.object(SimpleSalesAdmin, "get_exclude", lambda admin, request, obj=None: hidden):
            for key, spec in (
                ("group_by", SALES_BY_CLIENT),
                ("columns", {"report_model": "reporting_tests.SimpleSales", "kind": "list", "columns": ["value"]}),
                ("columns", {"report_model": "reporting_tests.SimpleSales", "columns": ["__total__"]}),
                (
                    "filters",
                    {
                        "report_model": "reporting_tests.SimpleSales",
                        "kind": "list",
                        "columns": ["date"],
                        "filters": {"client_id__in": [self.client1.pk]},
                    },
                ),
            ):
                with self.subTest(key=key, spec=spec):
                    out, err = self.call("run_dynamic_report", {"spec": spec})
                    self.assertTrue(err, out)
                    self.assertEqual(out["error"], "invalid_params")
                    self.assertEqual(out["fields"][key][0]["code"], "hidden_field")
            out, err = self.call("list_dynamic_report_models")
        self.assertFalse(err, out)
        models = {m["identifier"]: m for m in out["models"]}
        names = {f["name"] for f in models["reporting_tests.SimpleSales"]["fields"]}
        self.assertIn("date", names)
        self.assertFalse(names & set(hidden), names)

    def hidden_field_keys(self, spec, admin=SimpleSalesAdmin, hidden=("value",)):
        with mock.patch.object(admin, "get_exclude", lambda admin, request, obj=None: hidden):
            out, err = self.call("run_dynamic_report", {"spec": spec})
        self.assertTrue(err, out)
        self.assertEqual(out["detail"], "Invalid report spec.")
        return {key: [e["code"] for e in errors] for key, errors in out["fields"].items()}

    def test_every_spec_key_is_checked_against_hidden_fields(self):
        sales = {"report_model": "reporting_tests.SimpleSales", "group_by": "client", "columns": ["name"]}
        aggregate = {"method": "Sum", "field": "value", "name": "sales"}
        cases = [
            ("columns", {**sales, "columns": ["name", aggregate]}, ("value",)),
            ("date_field", {**sales, "date_field": "date", "start_date": f"{year}-01-01"}, ("date",)),
            ("time_series_columns", {**sales, "date_field": "date", "time_series_pattern": "monthly", "time_series_columns": [aggregate]}, ("value",)),
            ("crosstab_field", {**sales, "crosstab_field": "product", "crosstab_columns": ["__total__"]}, ("product",)),
            ("crosstab_columns", {**sales, "crosstab_field": "product", "crosstab_columns": [aggregate]}, ("value",)),
            ("filters", {**sales, "filters": {"product": self.product1.pk}}, ("product",)),
        ]
        for key, spec, hidden in cases:
            with self.subTest(key=key):
                self.assertEqual(self.hidden_field_keys(spec, hidden=hidden), {key: ["hidden_field"]})

    def test_related_model_fields_follow_the_related_admin(self):
        message = "Field 'Name' of Clients is not available."
        list_spec = {"report_model": "reporting_tests.SimpleSales", "kind": "list", "columns": ["client__name"]}
        group_spec = {"report_model": "reporting_tests.SimpleSales", "group_by": "client", "columns": ["name"]}
        for spec in (list_spec, group_spec):
            with self.subTest(spec=spec), mock.patch.object(ClientAdmin, "get_exclude", lambda admin, request, obj=None: ("name",)):
                out, err = self.call("run_dynamic_report", {"spec": spec})
                self.assertTrue(err, out)
                self.assertEqual(out["fields"], {"columns": [{"message": message, "code": "hidden_field"}]})

    def test_count_on_the_parent_pk_of_a_multi_table_child(self):
        RushOrder.objects.create(date_placed=f"{year}-01-02", client=self.client1, fee=5)
        RushOrder.objects.create(date_placed=f"{year}-01-03", client=self.client1, fee=7)
        spec = {
            "report_model": "reporting_tests.RushOrder",
            "group_by": "client",
            "columns": ["name", {"method": "Count", "field": "id", "name": "orders"}],
        }
        out, err = self.call("run_dynamic_report", {"spec": spec})
        self.assertFalse(err, out)
        self.assertEqual(out["rows"], [["Client 1", "2"]])
        out, err = self.call("list_dynamic_report_models")
        fields = {m["identifier"]: m["fields"] for m in out["models"]}["reporting_tests.RushOrder"]
        self.assertIn("id", [f["name"] for f in fields])

    def test_non_string_field_path_is_invalid_not_a_crash(self):
        spec = {"report_model": "reporting_tests.SimpleSales", "group_by": 5, "columns": ["value"]}
        out, err = self.call("run_dynamic_report", {"spec": spec})
        self.assertTrue(err, out)
        self.assertEqual(out["error"], "invalid_params")
        self.assertIn("group_by", out["fields"])

    def test_dynamic_report_error_details(self):
        out, err = self.call("run_dynamic_report", {"spec": 5})
        self.assertEqual((out["error"], out["detail"]), ("invalid_params", "'spec' must be an object."))
        out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT}, user=self.limited_user)
        self.assertEqual(out["detail"], "You may not view any kind of record a dynamic report could read.")
        out, err = self.call("run_dynamic_report", {"spec": {**SALES_BY_CLIENT, "group_by": "nope"}})
        self.assertEqual(out["detail"], "Invalid report spec.")
        denied = PermissionDenied("No view permission on reporting_tests.Client.")
        with mock.patch("erp_framework.reporting.mcp.run_dynamic_report", side_effect=denied):
            out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT})
        self.assertEqual((out["error"], out["detail"]), ("permission_denied", "You may not view one of the kinds of record in this report."))

    def test_user_model_is_not_listed_even_when_exposed(self):
        from django.contrib.auth import get_user_model

        from erp_framework.api import erp_api_site, erp_mcp_site

        user_model = get_user_model()
        exposed = [*erp_api_site.exposed_admins(), (user_model, erp_api_site.admin_site._registry[user_model])]
        request = RequestFactory().get("/")
        request.user = self.user
        with mock.patch.object(type(erp_api_site), "exposed_admins", lambda site: exposed), mock.patch.object(
            type(erp_mcp_site), "is_exposed", lambda site, model_admin: True
        ):
            self.assertNotIn(user_model, erp_mcp_site.get_dynamic_report_models(request))

    def test_list_display_fields_count_as_visible(self):
        spec = {"report_model": "reporting_tests.SimpleSales", "kind": "list", "columns": ["value"]}
        with mock.patch.object(SimpleSalesAdmin, "fields", [("slug", "date"), "client"]):
            out, err = self.call("run_dynamic_report", {"spec": spec})
        self.assertFalse(err, out)

    def test_list_kind_checks_columns_on_the_report_model(self):
        spec = {"report_model": "reporting_tests.SimpleSales", "kind": "list", "group_by": "client", "columns": ["slug"]}
        with mock.patch.object(ClientAdmin, "get_exclude", lambda admin, request, obj=None: ("slug",)):
            out, err = self.call("run_dynamic_report", {"spec": spec})
        self.assertNotIn("hidden_field", str(out.get("fields")))

    def test_computation_fields_check_their_queryset_model_and_requirements(self):
        from django.db.models import Sum
        from slick_reporting.fields import ComputationField
        from slick_reporting.registry import field_registry

        client_names = type(
            "ClientNames", (ComputationField,), {"name": "__client_names__", "calculation_field": "name", "queryset": Client.objects.all()}
        )
        value_total = type("ValueTotal", (ComputationField,), {"name": "__value_total__", "calculation_field": "value", "calculation_method": Sum})
        needs_value = type(
            "NeedsValue", (ComputationField,), {"name": "__needs_value__", "calculation_field": "quantity", "requires": [value_total]}
        )
        with mock.patch.dict(field_registry._registry, {f.name: f for f in (client_names, value_total, needs_value)}):
            for column, admin, hidden in (("__client_names__", ClientAdmin, ("name",)), ("__needs_value__", SimpleSalesAdmin, ("value",))):
                with self.subTest(column=column):
                    spec = {"report_model": "reporting_tests.SimpleSales", "group_by": "client", "columns": [column]}
                    self.assertEqual(self.hidden_field_keys(spec, admin=admin, hidden=hidden), {"columns": ["hidden_field"]})


@unittest.skipUnless(HAS_ADMIN_API, "needs django-admin-api-mcp")
@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class EntityListRowsTests(BaseTestData, TestCase):
    call = ReportToolsTests.call

    def test_api_list_rows_carry_the_name(self):
        out, err = self.call("list_objects", {"model": "reporting_tests.client"})
        self.assertFalse(err, out)
        self.assertEqual(out["columns"], ["id", "name", "slug", "notes"])
        self.assertIn("Client 1", {row[1] for row in out["rows"]})

    def test_html_changelist_keeps_the_title_column(self):
        from erp_framework.sites import erp_admin_site

        request = RequestFactory().get("/")
        request.user = self.user
        list_display = erp_admin_site._registry[Client].get_list_display(request)
        self.assertIn("get_enhanced_obj_title", list_display)
        self.assertNotIn("name", list_display)

    def test_spec_grammar_and_example(self):
        from erp_framework.api import erp_mcp_site
        from erp_framework.reporting.mcp import SPEC_EXAMPLE, SPEC_GUIDE

        out, err = self.call("list_dynamic_report_models")
        self.assertEqual((out["spec_guide"], out["spec_example"]), (SPEC_GUIDE, SPEC_EXAMPLE))
        self.assertIsInstance(SPEC_GUIDE, str)
        spec = {**SPEC_EXAMPLE, "report_model": "reporting_tests.SimpleSales", "start_date": f"{year}-01-01", "end_date": f"{year}-12-31"}
        out, err = self.call("run_dynamic_report", {"spec": spec})
        self.assertFalse(err, out)
        names = [c["name"] for c in out["columns"]]
        self.assertEqual((names[:2], len(names), names[2][:7]), (["name", "sales"], 14, "salesTS"))
        self.assertEqual([Decimal(row[1]) for row in out["rows"]], [sum(map(Decimal, row[2:])) for row in out["rows"]])
        example = {**SPEC_EXAMPLE, "report_model": "reporting_tests.SimpleSales"}
        self.assertFalse(self.call("run_dynamic_report", {"spec": example})[1])
        schema = {t.name: t.input_schema for t in erp_mcp_site.get_tools()}["run_dynamic_report"]
        self.assertIn("description", schema["properties"]["spec"])


@unittest.skipUnless(HAS_ADMIN_API, "needs django-admin-api-mcp")
@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class WithoutSlickRunnerTests(BaseTestData, TestCase):
    def test_api_imports_and_serves_admin_tools(self):
        import erp_framework.api

        spec = importlib.util.spec_from_file_location("erp_api_without_runner", erp_framework.api.__file__)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"slick_reporting.dynamic_report": None}):
            spec.loader.exec_module(module)
        self.assertFalse(module.HAS_REPORT_TOOLS)
        tool_names = {tool.name for tool in module.erp_mcp_site.get_tools()}
        self.assertIn("list_objects", tool_names)
        self.assertNotIn("run_report", tool_names)

        request = RequestFactory().post("/mcp/")
        request.user = self.user
        result = module.erp_mcp_site.call_tool(request, "list_objects", {"model": "reporting_tests.client"})
        self.assertFalse(result.is_error, result.data)
        self.assertEqual(result.data["count"], Client.objects.count())
        self.assertTrue(module.erp_api_site.urls)

    def test_runner_without_max_rows_serves_admin_tools(self):
        import erp_framework.api
        from slick_reporting.views import ReportViewBase

        spec = importlib.util.spec_from_file_location("erp_api_without_max_rows", erp_framework.api.__file__)
        module = importlib.util.module_from_spec(spec)
        del ReportViewBase.run_max_rows
        try:
            spec.loader.exec_module(module)
        finally:
            ReportViewBase.run_max_rows = None
        self.assertFalse(module.HAS_REPORT_TOOLS)


@unittest.skipUnless(HAS_ADMIN_API, "needs django-admin-api-mcp")
@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class ReportWordingTests(BaseTestData, TestCase):
    call = ReportToolsTests.call
    grant = DynamicReportToolTests.grant

    def assert_plain(self, out, *technical):
        text = str(out.get("detail", "")) + str(out.get("fields", ""))
        for word in technical:
            self.assertNotIn(word, text)

    def test_instructions_ask_for_labels_and_titles(self):
        from erp_framework.api import erp_mcp_site

        instructions = erp_mcp_site.instructions
        self.assertIn("Name reports by title, columns by label.", instructions)

    def test_hidden_field_message_uses_verbose_names(self):
        hidden = ("type", "client", "value")
        spec = {"report_model": "reporting_tests.SimpleSales", "kind": "list", "columns": ["value"]}
        with mock.patch.object(SimpleSalesAdmin, "get_exclude", lambda admin, request, obj=None: hidden):
            out, err = self.call("run_dynamic_report", {"spec": spec})
        self.assertTrue(err, out)
        message = out["fields"]["columns"][0]["message"]
        self.assertEqual(message, f"Field 'Value' of {SimpleSales._meta.verbose_name_plural} is not available.")
        self.assert_plain(out, "reporting_tests", "SimpleSales")

    def test_permission_refusals_carry_a_plain_detail(self):
        out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT}, user=self.limited_user)
        self.assertTrue(err)
        self.assertEqual(out["error"], "permission_denied")
        self.assertEqual(out["detail"], "You may not view any kind of record a dynamic report could read.")

        self.grant("view_client")
        denied = PermissionDenied("No view on reporting_tests.client")
        with mock.patch.object(ClientTotalBalance, "run", side_effect=denied):
            out, err = self.call("run_report", {"report": "client.balances"}, user=self.limited_user)
        self.assertTrue(err, out)
        self.assertEqual(out["detail"], "You may not view this report.")
        self.assert_plain(out, "reporting_tests")

    def test_slick_permission_message_is_not_passed_through(self):
        denied = PermissionDenied("No view permission on reporting_tests.SimpleSales.")
        with mock.patch("erp_framework.reporting.mcp.run_dynamic_report", side_effect=denied):
            out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT})
        self.assertTrue(err, out)
        self.assertEqual(out["detail"], "You may not view one of the kinds of record in this report.")
        self.assert_plain(out, "reporting_tests", "SimpleSales")

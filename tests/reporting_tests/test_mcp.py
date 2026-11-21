"""MCP report tools (erp_framework.reporting.mcp) over the registered test reports."""

import importlib.util
import sys
import unittest
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings

from erp_framework.reporting.models import UserReportPermission

from .admin import ClientAdmin, ProductAdmin, SimpleSalesAdmin
from .models import Client, SimpleSales
from .reports import ClientTotalBalance
from .tests import BaseTestData, year

HAS_ADMIN_API = importlib.util.find_spec("admin_api") is not None


@unittest.skipUnless(HAS_ADMIN_API, "needs django-admin-api-mcp")
@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class ReportToolsTests(BaseTestData, TestCase):
    def call(self, name, arguments=None, user=None, token=None):
        from erp_framework.api import erp_mcp_site

        request = RequestFactory().post("/mcp/")
        request.user = user or self.user
        if token is not None:
            request.api_token = token
        result = erp_mcp_site.call_tool(request, name, arguments or {})
        return result.data, result.is_error

    def run_report(self, report, params=None, **kwargs):
        out, err = self.call("run_report", {"report": report, "params": params or {}, **kwargs})
        self.assertFalse(err, out)
        return out

    def column_names(self, out):
        return [c["name"] for c in out["columns"]]

    def test_tools_are_listed_read_only(self):
        from erp_framework.api import erp_mcp_site

        tools = {t.name: t for t in erp_mcp_site.get_tools()}
        for name in ("list_reports", "describe_report", "run_report", "run_dynamic_report"):
            self.assertTrue(tools[name].annotations["readOnlyHint"], name)
            self.assertFalse(tools[name].writes, name)

    def test_list_reports_entry_carries_params_and_balance(self):
        out, err = self.call("list_reports")
        self.assertFalse(err, out)
        reports = {r["report"]: r for r in out["reports"]}
        self.assertEqual(
            reports["client.balances"],
            {
                "report": "client.balances",
                "title": "Clients Balances",
                "description": "Clients Balances",
                "base_model": "reporting_tests.client",
                "base_model_name": "Client",
                "kind": "group",
                "date_filter": False,
                "params": {"client_id": "reporting_tests.client", "product_id": "reporting_tests.product"},
                "balance": True,
                "columns": ["Identifier slug", "Name", "Closing Total", "Sum of value"],
            },
        )
        self.assertFalse(reports["client.clientdetailedstatement"]["balance"])
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

        site = OneRowSite(erp_api_site, name="one_row_mcp")
        request = RequestFactory().post("/mcp/")
        request.user = self.user
        result = site.call_tool(request, "run_report", {"report": "client.balances", "max_rows": 10_000})
        self.assertFalse(result.is_error, result.data)
        self.assertEqual(len(result.data["rows"]), 1)
        self.assertTrue(result.data["truncated"])

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
        self.assertIn("7. Reports: run one from the report catalog above with run_report", instructions)
        self.assertIn("Note: run a catalog report directly for a kind of record", instructions)
        self.assertIn("Note: answer totals and balances with a report, not list_objects rows", instructions)
        self.assertIn("call list_reports when there is none", instructions)
        self.assertNotIn("look them up with list_objects", instructions)
        for item in ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8."):
            self.assertEqual(instructions.count(f"\n{item} "), 1, item)
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
            out, err = self.call("run_report", {"report": "client.balances", "params": {"client_id": [self.client2.pk]}})
        self.assertTrue(err, out)
        self.assertEqual(out["error"], "invalid_params")
        self.assertIn("client_id", out["fields"])

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
        out, err = self.call("list_reports", user=self.limited_user)
        self.assertFalse(err, out)
        self.assertTrue(out["reports"])
        self.assertTrue(all(r["base_model"] == "reporting_tests.client" for r in out["reports"]))

    def test_token_scope_narrows_reports(self):
        token = type("Token", (), {"scopes": ["reporting_tests.product:view"], "prefix": "t"})()
        out, err = self.call("list_reports", token=token)
        self.assertFalse(err, out)
        self.assertTrue(out["reports"])
        self.assertTrue(all(r["base_model"] == "reporting_tests.product" for r in out["reports"]))

    def test_token_scope_checks_report_model_without_base_model(self):
        token = type("Token", (), {"scopes": ["reporting_tests.product:view"], "prefix": "t"})()
        with mock.patch.object(ClientTotalBalance, "base_model", None):
            out, err = self.call("list_reports", token=token)
        self.assertFalse(err, out)
        self.assertTrue(all(r["base_model"] == "reporting_tests.product" for r in out["reports"]), out["reports"])

    def test_is_report_exposed_hides_reports(self):
        from erp_framework.api import ERPMcpSite, erp_api_site

        class ProductOnlySite(ERPMcpSite):
            def is_report_exposed(self, report_class):
                return report_class.get_base_model_name() == "product"

        site = ProductOnlySite(erp_api_site, name="product_only_mcp")
        request = RequestFactory().post("/mcp/")
        request.user = self.user
        result = site.call_tool(request, "list_reports", {})
        self.assertFalse(result.is_error, result.data)
        self.assertTrue(all(r["report"].startswith("product.") for r in result.data["reports"]))


@unittest.skipUnless(HAS_ADMIN_API, "needs django-admin-api-mcp")
@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class ReportRoutingTests(BaseTestData, TestCase):
    call = ReportToolsTests.call

    def request(self, user=None):
        request = RequestFactory().post("/mcp/")
        request.user = user or self.user
        return request

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

    def catalog(self, instructions):
        """The catalog lines at the top of ``instructions``, or None without a catalog."""
        if not instructions.startswith("Report catalog"):
            return None
        return instructions.split("\n\n", 1)[0].splitlines()[1:]

    def test_instructions_start_with_the_users_report_catalog(self):
        from erp_framework.api import erp_mcp_site

        instructions = erp_mcp_site.get_instructions(self.request())
        self.assertTrue(instructions.startswith("Report catalog (code: question; params; balance"))
        self.assertTrue(instructions.endswith("\n\n" + erp_mcp_site.instructions))
        self.assertLessEqual(len(instructions), 4096)
        lines = self.catalog(instructions)
        self.assertEqual(len(lines), len(self.call("list_reports")[0]["reports"]))
        self.assertIn("client.balances: Clients Balances; client_id, product_id; balance", lines)

    def test_catalog_drops_detail_to_fit(self):
        from erp_framework.api import erp_mcp_site

        full = erp_mcp_site.get_instructions(self.request())
        for budget, header, line in (
            (len(full) - 1, "Report catalog (code; params;", "client.balances; client_id, product_id"),
            (len(erp_mcp_site.instructions) + 600, "Report catalog (codes;", "client.balances"),
        ):
            with mock.patch.object(type(erp_mcp_site), "instructions_max_chars", budget):
                instructions = erp_mcp_site.get_instructions(self.request())
            self.assertTrue(instructions.startswith(header), instructions[:100])
            self.assertLessEqual(len(instructions), budget)
            self.assertIn(line, self.catalog(instructions))

    def test_pilot_sized_catalog_fits_in_4096_characters(self):
        from erp_framework.api import erp_mcp_site

        # 24 reports with codes, questions and params as long as a downstream services ERP's
        entries = [
            {
                "report": f"service.service-sales-summary-{n:02d}",
                "description": "Who are our top clients for services, by net sales in the period?",
                "params": {"client_id": "x", "service_id": "x"},
                "balance": True,
            }
            for n in range(24)
        ]
        reports = [ClientTotalBalance] * 24
        with mock.patch.object(type(erp_mcp_site), "get_reports", lambda site, request, code=None: reports), \
                mock.patch("erp_framework.reporting.mcp.report_entry", side_effect=entries):
            instructions = erp_mcp_site.get_instructions(self.request())
        self.assertLessEqual(len(instructions), 4096)
        self.assertEqual(len(self.catalog(instructions)), 24)
        self.assertTrue(instructions.endswith(erp_mcp_site.instructions))

    def test_catalog_lists_only_reports_the_user_may_run(self):
        from erp_framework.api import erp_mcp_site

        UserReportPermission.objects.create(
            user=self.limited_user, report_code=ClientTotalBalance.get_report_code(), view=True
        )
        lines = self.catalog(erp_mcp_site.get_instructions(self.request(self.limited_user)))
        self.assertEqual(lines, ["client.balances: Clients Balances; client_id, product_id; balance"])

    def test_catalog_is_left_out_when_it_does_not_fit_or_without_a_user(self):
        from django.contrib.auth.models import AnonymousUser

        from erp_framework.api import erp_mcp_site

        reports = self.call("list_reports")[0]["reports"]
        with mock.patch.object(type(erp_mcp_site), "report_catalog_max", len(reports) - 1):
            self.assertEqual(erp_mcp_site.get_instructions(self.request()), erp_mcp_site.instructions)
        with mock.patch.object(type(erp_mcp_site), "instructions_max_chars", len(erp_mcp_site.instructions) + 50):
            self.assertEqual(erp_mcp_site.get_instructions(self.request()), erp_mcp_site.instructions)
        self.assertEqual(erp_mcp_site.get_instructions(self.request(AnonymousUser())), erp_mcp_site.instructions)


SALES_BY_CLIENT = {
    "report_model": "reporting_tests.SimpleSales",
    "group_by": "client",
    "columns": ["name", {"method": "Sum", "field": "value", "name": "sales"}],
}


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

    def test_bad_spec_is_invalid_params(self):
        spec = {**SALES_BY_CLIENT, "columns": [{"method": "Sum", "field": "no_such_field"}]}
        out, err = self.call("run_dynamic_report", {"spec": spec})
        self.assertTrue(err)
        self.assertEqual(out["error"], "invalid_params")
        self.assertIn("columns", out["fields"])

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
        token = type("Token", (), {"scopes": ["reporting_tests.product:view"], "prefix": "t"})()
        out, err = self.call("list_dynamic_report_models", token=token)
        self.assertFalse(err, out)
        self.assertEqual({m["identifier"] for m in out["models"]}, {"reporting_tests.Product"})
        out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT}, token=token)
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
        request = RequestFactory().post("/mcp/")
        request.user = self.user
        result = site.call_tool(request, "list_dynamic_report_models", {})
        self.assertFalse(result.is_error, result.data)
        identifiers = {m["identifier"] for m in result.data["models"]}
        self.assertIn("reporting_tests.SimpleSales", identifiers)
        self.assertNotIn("reporting_tests.Product", identifiers)

        for key, spec in (
            ("report_model", {"report_model": "reporting_tests.Product", "kind": "list", "columns": ["name"]}),
            ("group_by", {**SALES_BY_CLIENT, "group_by": "product"}),
        ):
            with self.subTest(key=key):
                result = site.call_tool(request, "run_dynamic_report", {"spec": spec})
                self.assertTrue(result.is_error, result.data)
                self.assertEqual(result.data["fields"][key][0]["code"], "model_not_allowed")

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


@unittest.skipUnless(HAS_ADMIN_API, "needs django-admin-api-mcp")
@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class ReportWordingTests(BaseTestData, TestCase):
    call = ReportToolsTests.call

    def assert_plain(self, out, *technical):
        text = str(out.get("detail", "")) + str(out.get("fields", ""))
        for word in technical:
            self.assertNotIn(word, text)

    def test_instructions_ask_for_labels_and_titles(self):
        from erp_framework.api import erp_mcp_site

        instructions = erp_mcp_site.instructions
        self.assertIn("Name a report by its 'title', a column and a record by its label.", instructions)

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

        self.limited_user.user_permissions.add(*Permission.objects.filter(codename__in=["view_client"]))
        self.limited_user = type(self.limited_user).objects.get(pk=self.limited_user.pk)
        denied = PermissionDenied("No view on reporting_tests.client")
        with mock.patch.object(ClientTotalBalance, "run", side_effect=denied):
            out, err = self.call("run_report", {"report": "client.balances"}, user=self.limited_user)
        self.assertTrue(err, out)
        self.assertEqual(out["detail"], "You may not view this report.")
        self.assert_plain(out, "reporting_tests")

    def test_slick_permission_message_is_not_passed_through(self):
        from slick_reporting import dynamic_report

        denied = PermissionDenied("No view permission on reporting_tests.SimpleSales.")
        with mock.patch.object(dynamic_report, "run_dynamic_report", side_effect=denied), mock.patch(
            "erp_framework.reporting.mcp.run_dynamic_report", side_effect=denied
        ):
            out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT})
        self.assertTrue(err, out)
        self.assertEqual(out["detail"], "You may not view one of the kinds of record in this report.")
        self.assert_plain(out, "reporting_tests", "SimpleSales")

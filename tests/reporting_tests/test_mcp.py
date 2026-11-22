"""MCP report tools (erp_framework.reporting.mcp) over the registered test reports."""

import importlib.util
import sys
import unittest
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Permission
from django.core.exceptions import NON_FIELD_ERRORS, PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase, override_settings

from erp_framework.reporting.models import UserReportPermission

from .admin import ClientAdmin, ProductAdmin, SimpleSalesAdmin
from .models import Client, Product, SimpleSales
from .reports import ClientTotalBalance
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

    def test_list_reports_exposes_every_registered_report(self):
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
                "kind": "group",
                "date_filter": False,
            },
        )
        self.assertEqual(reports["product.productclientsalesmatrix"]["kind"], "crosstab")
        self.assertEqual(reports["client.clientsalesmonthlyseries"]["kind"], "series")
        self.assertEqual(reports["client.clientdetailedstatement"]["kind"], "list")

    def test_describe_report(self):
        out, err = self.call("describe_report", {"report": "product.productclientsalesmatrix"})
        self.assertFalse(err, out)
        self.assertEqual(out["kind"], "crosstab")
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
        out, err = self.call("list_reports", token=PRODUCT_TOKEN)
        self.assertFalse(err, out)
        self.assertTrue(out["reports"])
        self.assertTrue(all(r["base_model"] == "reporting_tests.product" for r in out["reports"]))

    def test_token_scope_checks_report_model_without_base_model(self):
        with mock.patch.object(ClientTotalBalance, "base_model", None):
            out, err = self.call("list_reports", token=PRODUCT_TOKEN)
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
        max_rows = {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200}
        self.assertEqual(schemas["list_reports"]["properties"], {})
        self.assertEqual(schemas["describe_report"]["required"], ["report"])
        self.assertEqual(schemas["describe_report"]["properties"]["report"]["type"], "string")
        self.assertIn("description", schemas["describe_report"]["properties"]["report"])
        run = schemas["run_report"]
        self.assertEqual(run["required"], ["report"])
        self.assertEqual(set(run["properties"]), {"report", "params", "max_rows"})
        self.assertEqual(run["properties"]["params"]["type"], "object")
        self.assertIn("description", run["properties"]["params"])
        self.assertEqual({k: run["properties"]["max_rows"][k] for k in max_rows}, max_rows)
        self.assertIn("description", run["properties"]["max_rows"])
        dynamic = schemas["run_dynamic_report"]
        self.assertEqual(dynamic["required"], ["spec"])
        self.assertEqual(dynamic["properties"]["max_rows"], run["properties"]["max_rows"])
        self.assertIs(dynamic["properties"]["spec"], SPEC_SCHEMA)
        self.assertNotIn("$schema", SPEC_SCHEMA)
        self.assertEqual(SPEC_SCHEMA["type"], "object")

    def test_instructions_add_the_report_items(self):
        from erp_framework.api import erp_mcp_site
        from erp_framework.reporting.mcp import DEFAULT_INSTRUCTIONS, REPORT_INSTRUCTIONS

        self.assertEqual(erp_mcp_site.instructions, DEFAULT_INSTRUCTIONS + REPORT_INSTRUCTIONS)

    def test_report_description_falls_back_from_attribute_to_docstring_to_title(self):
        def description():
            out, err = self.call("list_reports")
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
                "report_model": "reporting_tests.simplesales",
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
        message = "Field 'name' of reporting_tests.Client is not available."
        list_spec = {"report_model": "reporting_tests.SimpleSales", "kind": "list", "columns": ["client__name"]}
        group_spec = {"report_model": "reporting_tests.SimpleSales", "group_by": "client", "columns": ["name"]}
        for spec in (list_spec, group_spec):
            with self.subTest(spec=spec), mock.patch.object(ClientAdmin, "get_exclude", lambda admin, request, obj=None: ("name",)):
                out, err = self.call("run_dynamic_report", {"spec": spec})
                self.assertTrue(err, out)
                self.assertEqual(out["fields"], {"columns": [{"message": message, "code": "hidden_field"}]})

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
        self.assertEqual(out["detail"], "You may not view any model a dynamic report could read.")
        out, err = self.call("run_dynamic_report", {"spec": {**SALES_BY_CLIENT, "group_by": "nope"}})
        self.assertEqual(out["detail"], "Invalid report spec.")
        denied = PermissionDenied("No view permission on reporting_tests.Client.")
        with mock.patch("erp_framework.reporting.mcp.run_dynamic_report", side_effect=denied):
            out, err = self.call("run_dynamic_report", {"spec": SALES_BY_CLIENT})
        self.assertEqual((out["error"], out["detail"]), ("permission_denied", "No view permission on reporting_tests.Client."))

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

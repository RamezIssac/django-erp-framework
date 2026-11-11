"""MCP (django-admin-api's AdminMcpSite) over erp_framework admins: same hooks as HTML and JSON."""

import importlib.util
import json
import unittest

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from reversion.models import Version

from erp_framework.admin.admin import changeform_saved
from erp_framework.api import erp_mcp_site

from . import admin as api_admin
from .models import Customer, Item, Order, OrderLine

HAS_MCP_SDK = importlib.util.find_spec("mcp") is not None


@override_settings(ROOT_URLCONF="api_tests.urls", USE_TZ=True)
class ErpMcpTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser("root", "r@x.io", "pw")
        stamp = {"owner": cls.user, "lastmod_user": cls.user, "lastmod": timezone.now()}
        cls.customer = Customer.objects.create(name="Ahmed", slug="c1", **stamp)
        cls.cheese = Item.objects.create(name="Cheese", slug="i1", **stamp)

    def setUp(self):
        api_admin.calls.clear()
        self.signals = []
        changeform_saved.connect(self._on_saved)

    def tearDown(self):
        changeform_saved.disconnect(self._on_saved)

    def _on_saved(self, sender, instance, created, request=None, **kwargs):
        self.signals.append((sender.__name__, created, getattr(request, "is_dry_run", None)))

    def call(self, name, arguments):
        request = RequestFactory().post("/mcp/")
        request.user = self.user
        result = erp_mcp_site.call_tool(request, name, arguments)
        return result.data, result.is_error

    def order_data(self, **extra):
        return {
            "slug": "1",
            "date": "2025-03-01T10:00:00+00:00",
            "customer": self.customer.pk,
            "inlines": {"lines": [{"item": self.cheese.pk, "quantity": "2", "price": "10"}]},
            **extra,
        }

    def test_lists_erp_models(self):
        out, err = self.call("list_models", {})
        self.assertFalse(err)
        self.assertTrue(
            {"api_tests.customer", "api_tests.item", "api_tests.order"} <= {m["model"] for m in out["models"]}
        )

    def test_describe_order(self):
        out, err = self.call("describe_model", {"model": "api_tests.order"})
        self.assertFalse(err, out)
        create = out["input_schema"]["create"]
        self.assertIn("customer", create["required"])
        self.assertIn("lines", create["properties"]["inlines"]["properties"])

    def test_create_runs_erp_hooks(self):
        out, err = self.call("create_object", {"model": "api_tests.order", "data": self.order_data()})
        self.assertFalse(err, out)
        order = Order.objects.get(pk=out["object"]["pk"])
        self.assertEqual(out["object"]["value"], "20.00")  # post_save recomputed it
        self.assertEqual(
            api_admin.calls, [("whole_changeform_validation", True), ("pre_save", False), ("post_save", False)]
        )
        self.assertEqual(self.signals, [("Order", True, False)])
        self.assertEqual(order.owner, self.user)
        self.assertEqual(Version.objects.get_for_object(order).count(), 1)

    def test_dry_run_runs_hooks_then_rolls_back(self):
        out, err = self.call("create_object", {"model": "api_tests.order", "data": self.order_data(), "dry_run": True})
        self.assertFalse(err, out)
        self.assertTrue(out["valid"])
        self.assertEqual(out["object"]["value"], "20.00")
        self.assertEqual(
            api_admin.calls, [("whole_changeform_validation", True), ("pre_save", False), ("post_save", False)]
        )
        # the signal fires during a dry run; receivers can tell from request.is_dry_run
        self.assertEqual(self.signals, [("Order", True, True)])
        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderLine.objects.exists())
        self.assertFalse(LogEntry.objects.exists())
        self.assertFalse(Version.objects.exists())

    def test_dry_run_reports_whole_changeform_validation(self):
        out, err = self.call(
            "create_object", {"model": "api_tests.order", "data": self.order_data(notes="reject"), "dry_run": True}
        )
        self.assertFalse(err)
        self.assertEqual(
            out,
            {
                "dry_run": True,
                "valid": False,
                "errors": {"non_field_errors": ["Rejected by whole_changeform_validation."]},
            },
        )
        self.assertEqual(self.signals, [])

    def test_rejected_write_is_an_error(self):
        out, err = self.call("create_object", {"model": "api_tests.order", "data": self.order_data(notes="reject")})
        self.assertTrue(err)
        self.assertEqual(out["error"], "validation_failed")
        self.assertFalse(Order.objects.exists())

    @unittest.skipUnless(HAS_MCP_SDK, "needs django-admin-api[mcp]")
    def test_http_endpoint(self):
        from admin_api.models import ApiToken

        _, raw = ApiToken.objects.create_token(self.user, "mcp", kind="mcp")
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "list_objects", "arguments": {"model": "api_tests.customer"}},
        }
        resp = self.client.post(
            "/mcp/",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_ACCEPT="application/json, text/event-stream",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
            HTTP_MCP_PROTOCOL_VERSION="2025-06-18",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        result = json.loads(resp.content)["result"]["structuredContent"]
        self.assertEqual(result["count"], 1)
        self.assertIn("c1", result["rows"][0])  # EntityAdmin lists the slug

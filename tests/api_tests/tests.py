"""django-admin-api against erp_framework admins: same hooks for HTML and JSON writes."""

import datetime
import json
from decimal import Decimal

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from reversion.models import Version

from erp_framework.admin.admin import changeform_saved

from . import admin as api_admin
from .models import Customer, Item, Order, OrderLine

LIST = "/api/v1/api_tests/order/"


@override_settings(ROOT_URLCONF="api_tests.urls", USE_TZ=True)
class ErpApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser("root", "r@x.io", "pw")
        stamp = {"owner": cls.user, "lastmod_user": cls.user, "lastmod": timezone.now()}
        cls.customer = Customer.objects.create(name="Ahmed", slug="c1", **stamp)
        cls.cheese = Item.objects.create(name="Cheese", slug="i1", **stamp)
        cls.milk = Item.objects.create(name="Milk", slug="i2", **stamp)

    def setUp(self):
        api_admin.calls.clear()
        self.client.force_login(self.user)
        self.signals = []
        changeform_saved.connect(self._on_saved)

    def tearDown(self):
        changeform_saved.disconnect(self._on_saved)

    def _on_saved(self, sender, instance, created, **kwargs):
        self.signals.append((sender.__name__, created))

    def api(self, method, url, payload=None):
        if method == "get":
            resp = self.client.get(url)
        else:
            resp = getattr(self.client, method)(url, data=json.dumps(payload or {}), content_type="application/json")
        return resp.status_code, json.loads(resp.content)

    def create_order(self, **extra):
        payload = {
            "slug": "1",
            "date": "2025-03-01T10:00:00+00:00",
            "customer": self.customer.pk,
            "inlines": {
                "lines": [
                    {"item": self.cheese.pk, "quantity": "2", "price": "10"},
                    {"item": self.milk.pk, "quantity": "1", "price": "5"},
                ]
            },
        }
        payload.update(extra)
        return self.api("post", LIST, payload)

    # ---------------------------------------------------------------------------------------
    def test_create_runs_erp_hooks(self):
        status, body = self.create_order()
        self.assertEqual(status, 201, body)
        order = Order.objects.get(pk=body["pk"])
        self.assertEqual(
            api_admin.calls,
            [("whole_changeform_validation", True), ("pre_save", False), ("post_save", False)],
        )
        self.assertEqual(self.signals, [("Order", True)])
        # EntityAdmin.save_model stamps the owner; TransactionAdmin.save_formset copies FKs/date to lines
        self.assertEqual(order.owner, self.user)
        lines = list(order.lines.order_by("pk"))
        self.assertEqual(
            [(line.item.name, line.customer_id) for line in lines],
            [("Cheese", self.customer.pk), ("Milk", self.customer.pk)],
        )
        self.assertTrue(all(line.date == order.date for line in lines))
        # post_save recomputed the value from the lines (2*10 + 1*5)
        self.assertEqual(order.value, Decimal("25.00"))
        self.assertEqual(body["value"], "25.00")
        self.assertEqual(order.date, datetime.datetime(2025, 3, 1, 10, 0, tzinfo=datetime.timezone.utc))
        self.assertEqual(LogEntry.objects.get(object_id=str(order.pk)).action_flag, ADDITION)
        # VersionAdmin: the API opened a reversion revision
        self.assertEqual(Version.objects.get_for_object(order).count(), 1)

    def test_whole_changeform_validation_rejects(self):
        status, body = self.create_order(notes="reject")
        self.assertEqual(status, 400)
        self.assertEqual(body["non_field_errors"], ["Rejected by whole_changeform_validation."])
        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderLine.objects.exists())
        self.assertNotIn(("pre_save", False), api_admin.calls)
        self.assertEqual(self.signals, [])

    def test_patch_runs_hooks_and_updates_lines(self):
        _, body = self.create_order()
        order = Order.objects.get(pk=body["pk"])
        cheese_line = order.lines.get(item=self.cheese)
        milk_line = order.lines.get(item=self.milk)
        api_admin.calls.clear()
        status, body = self.api(
            "patch",
            f"{LIST}{order.pk}/",
            {"notes": "rush", "inlines": {"lines": [{"pk": cheese_line.pk, "quantity": "3"}, {"pk": milk_line.pk, "_delete": True}]}},
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(
            api_admin.calls,
            [("whole_changeform_validation", True), ("pre_save", True), ("post_save", True)],
        )
        order.refresh_from_db()
        self.assertEqual(order.notes, "rush")
        self.assertEqual(order.value, Decimal("30.00"))
        self.assertEqual(list(order.lines.values_list("item__name", flat=True)), ["Cheese"])
        self.assertEqual(LogEntry.objects.filter(object_id=str(order.pk), action_flag=CHANGE).count(), 1)
        self.assertEqual(Version.objects.get_for_object(order).count(), 2)

    def test_html_change_form_still_runs_hooks(self):
        """Regression for the refactor: the HTML admin goes through process_changeform too."""
        url = "/admin/api_tests/order/add/"
        self.assertEqual(self.client.get(url).status_code, 200)
        data = {
            "slug": "7",
            "date_0": "2025-03-01",
            "date_1": "10:00:00",
            "customer": self.customer.pk,
            "notes": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-item": self.cheese.pk,
            "lines-0-quantity": "4",
            "lines-0-price": "10",
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302, getattr(resp, "context_data", {}).get("errors"))
        order = Order.objects.get(slug="7")
        self.assertEqual(order.value, Decimal("40.00"))
        self.assertEqual(
            api_admin.calls,
            [("whole_changeform_validation", False), ("pre_save", False), ("post_save", False)],
        )
        # and rejection re-renders the form with the error
        api_admin.calls.clear()
        data.update(slug="8", notes="reject")
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Rejected by whole_changeform_validation.")
        self.assertFalse(Order.objects.filter(slug="8").exists())

    def test_list_and_detail(self):
        _, created = self.create_order()
        status, body = self.api("get", LIST)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["count"], 1)
        row = body["results"][0]
        # HTML-producing callables of TransactionAdmin's list_display are not exposed
        self.assertNotIn("get_history_link", row)
        status, detail = self.api("get", f"{LIST}{created['pk']}/")
        self.assertEqual(status, 200)
        self.assertEqual(detail["customer"], {"pk": self.customer.pk, "str": "Ahmed"})
        self.assertEqual(len(detail["inlines"]["lines"]), 2)

    def test_registry_lists_erp_models(self):
        status, body = self.api("get", "/api/v1/")
        self.assertEqual(status, 200)
        models = {m["model"] for app in body["apps"] for m in app["models"]}
        self.assertTrue({"customer", "item", "order"} <= models)

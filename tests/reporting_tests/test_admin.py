from unittest import mock

from django import test
from django.contrib.admin.models import LogEntry
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from pyquery import PyQuery as pq
from erp_framework.activity.admin import LogEntryAdmin
from erp_framework.admin.admin import (
    EntityAdmin,
    RaMovementPrepopulatedAdmin,
    RaPrePopulatedAdmin,
    TransactionAdmin,
)
from erp_framework.base import app_settings
from erp_framework.sites import erp_admin_site
from .models import Client, Product, Invoice, InvoiceLine, SaleDocType, SimpleSales

User = get_user_model()


@test.override_settings(ROOT_URLCONF="reporting_tests.urls")
class TestAdminFunctionality(test.TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin = User.objects.create_superuser(
            username="admin", password="admin", email=""
        )
        cls.client1 = Client.objects.create(name="Client 1", owner_id=cls.admin.pk)

    def test_admin_client_view(self):
        self.client.login(username="admin", password="admin")
        response = self.client.get(
            reverse("erp_framework:reporting_tests_client_view", args=[self.client1.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_client_changelist(self):
        self.client.login(username="admin", password="admin")
        response = self.client.get(
            reverse("erp_framework:reporting_tests_client_changelist")
        )
        self.assertEqual(response.status_code, 200)

    def test_reversion_pages_show_title(self):
        self.client.login(username="admin", password="admin")
        pages = {
            "erp_framework:reporting_tests_client_recoverlist": ([], "Recover deleted Clients"),
            "erp_framework:reporting_tests_client_history": (
                [self.client1.pk],
                "Change history: Client 1",
            ),
        }
        for url_name, (args, title) in pages.items():
            with self.subTest(url_name):
                response = self.client.get(reverse(url_name, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(pq(response.content)("h2.page-title").text(), title)

    def test_delete_selected_needs_the_delete_all_setting(self):
        self.client.login(username="admin", password="admin")
        url = reverse("erp_framework:reporting_tests_client_changelist")
        self.assertNotContains(self.client.get(url), 'value="delete_selected"')
        with mock.patch.object(app_settings, "ERP_FRAMEWORK_ENABLE_ADMIN_DELETE_ALL", True):
            response = self.client.get(url)
            actions = erp_admin_site._registry[Client].get_actions(response.wsgi_request)
        self.assertContains(response, 'value="delete_selected"')
        self.assertIn("delete_selected", actions)


@test.override_settings(ROOT_URLCONF="reporting_tests.urls")
class TestAdminDescription(test.TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin_user = User.objects.create_superuser(
            username="admin", password="admin", email=""
        )

    def get_context(self, admin_class, model):
        request = RequestFactory().get("/")
        request.user = self.admin_user
        model_admin = admin_class(model, erp_admin_site)
        return model_admin.changelist_view(request).context_data

    def test_description_in_changelist_context(self):
        bases = [
            (EntityAdmin, Client),
            (TransactionAdmin, SimpleSales),
            (RaPrePopulatedAdmin, Client),
            (RaMovementPrepopulatedAdmin, Client),
            (LogEntryAdmin, LogEntry),
        ]
        for base, model in bases:
            with self.subTest(base=base.__name__):
                admin_class = type("Described", (base,), {"description": "About it"})
                self.assertEqual(self.get_context(admin_class, model)["description"], "About it")

    def test_description_defaults_to_none(self):
        for base, model in [(EntityAdmin, Client), (TransactionAdmin, SimpleSales), (LogEntryAdmin, LogEntry)]:
            with self.subTest(base=base.__name__):
                self.assertIsNone(self.get_context(base, model)["description"])

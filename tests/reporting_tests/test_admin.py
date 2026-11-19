from django import test
from django.contrib.admin.models import LogEntry
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from erp_framework.activity.admin import LogEntryAdmin
from erp_framework.admin.admin import (
    EntityAdmin,
    RaMovementPrepopulatedAdmin,
    RaPrePopulatedAdmin,
    TransactionAdmin,
)
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

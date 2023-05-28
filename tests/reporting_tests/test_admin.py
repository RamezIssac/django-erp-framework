from django import test
from django.contrib.auth import get_user_model
from django.urls import reverse
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

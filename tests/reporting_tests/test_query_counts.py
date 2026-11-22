from django.test import TestCase, override_settings
from django.urls import reverse

from .tests import BaseTestData

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class QueryCountTest(BaseTestData, TestCase):
    """Pins the queries each report type and the entity changelist run per request."""

    def assertGetNumQueries(self, num, url, **extra):
        self.client.get(url, **extra)  # warm the ContentType and Site caches
        with self.assertNumQueries(num):
            response = self.client.get(url, **extra)
        self.assertEqual(response.status_code, 200)

    def setUp(self):
        self.client.force_login(self.user)

    def test_reports(self):
        for base_model, slug, num, extra in (
            ("client", "balances", 9, AJAX),  # group by
            ("client", "clientsalesmonthlyseries", 59, AJAX),  # time series
            ("product", "productclientsalesmatrix", 7, AJAX),  # crosstab
            ("client", "clientdetailedstatement", 3, AJAX),  # list
            ("client", "balances", 6, {}),  # report page
        ):
            with self.subTest(slug, ajax=bool(extra)):
                url = reverse("erp_framework:report", args=(base_model, slug))
                self.assertGetNumQueries(num, url, **extra)

    def test_entity_changelist(self):
        url = reverse("erp_framework:reporting_tests_client_changelist")
        self.assertGetNumQueries(11, url)

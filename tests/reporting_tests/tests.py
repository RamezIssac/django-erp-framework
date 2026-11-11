import datetime
from unittest import skip
from urllib.parse import urljoin

from django.contrib.admin.sites import NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now
from pyquery import PyQuery as pq
from slick_reporting.generator import ReportGenerator

from erp_framework.activity.admin import ActionFilter, RAContentTypeFilter
from erp_framework.activity.models import MyActivity

from .models import Client, Product, SimpleSales, InvoiceLine, Journal

User = get_user_model()
SUPER_LOGIN = dict(username="superlogin", password="password")
year = now().year


def get_rows(data):
    """
    Reassemble a report JSON response into a list of row dicts.

    django-slick-reporting >= 1.5.0 returns ``data`` columnar (a dict mapping
    column name -> list of values, one per row); the assertions here are
    written against the row-oriented list, rebuilt via the shipped helper.
    """
    columns = [column["name"] for column in data["columns"]]
    return ReportGenerator.columns_to_rows(data["data"], columns)


class BaseTestData:
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        User.objects.create_superuser("super", None, "secret")

        user = User.objects.create(is_superuser=True, is_staff=True, **SUPER_LOGIN)
        limited_user = User.objects.create_user(
            is_superuser=False, is_staff=True, username="limited", password="password"
        )
        cls.user = user
        cls.limited_user = limited_user
        cls.client1 = Client.objects.create(name="Client 1", lastmod_user=user)
        cls.client2 = Client.objects.create(name="Client 2", lastmod_user=user)
        cls.client3 = Client.objects.create(name="Client 3", lastmod_user=user)
        cls.clientIdle = Client.objects.create(name="Client Idle", lastmod_user=user)

        cls.product1 = Product.objects.create(name="Product 1", lastmod_user=user)
        cls.product2 = Product.objects.create(name="Product 2", lastmod_user=user)
        cls.product3 = Product.objects.create(name="Product 3", lastmod_user=user)

        SimpleSales.objects.create(
            slug=1,
            date=datetime.datetime(year, 1, 2),
            client=cls.client1,
            product=cls.product1,
            quantity=10,
            price=10,
            lastmod_user=user,
        )
        SimpleSales.objects.create(
            slug=1,
            date=datetime.datetime(year, 2, 2),
            client=cls.client1,
            product=cls.product1,
            quantity=10,
            price=10,
            lastmod_user=user,
        )

        SimpleSales.objects.create(
            slug=1,
            date=datetime.datetime(year, 3, 2),
            client=cls.client1,
            product=cls.product1,
            quantity=10,
            price=10,
            lastmod_user=user,
        )

        # client 2
        SimpleSales.objects.create(
            slug=1,
            date=datetime.datetime(year, 1, 2),
            client=cls.client2,
            product=cls.product1,
            quantity=20,
            price=10,
            lastmod_user=user,
        )
        SimpleSales.objects.create(
            slug=1,
            date=datetime.datetime(year, 2, 2),
            client=cls.client2,
            product=cls.product1,
            quantity=20,
            price=10,
            lastmod_user=user,
        )

        SimpleSales.objects.create(
            slug=1,
            date=datetime.datetime(year, 3, 2),
            client=cls.client2,
            product=cls.product1,
            quantity=20,
            price=10,
            lastmod_user=user,
        )

        # client 3
        SimpleSales.objects.create(
            slug=1,
            date=datetime.datetime(year, 1, 2),
            client=cls.client3,
            product=cls.product1,
            quantity=30,
            price=10,
            lastmod_user=user,
        )
        SimpleSales.objects.create(
            slug=1,
            date=datetime.datetime(year, 2, 2),
            client=cls.client3,
            product=cls.product1,
            quantity=30,
            price=10,
            lastmod_user=user,
        )

        SimpleSales.objects.create(
            slug=1,
            date=datetime.datetime(year, 3, 2),
            client=cls.client3,
            product=cls.product1,
            quantity=30,
            price=10,
            lastmod_user=user,
        )


@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class ReportTest(BaseTestData, TestCase):
    def test_client_balance(self):
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse("erp_framework:report", args=("client", "balances")),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        rows = get_rows(response.json())
        self.assertEqual(rows[0].get("__balance__"), 300, rows[0])

    def test_product_total_sales(self):
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse("erp_framework:report", args=("product", "total_sales")),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        rows = get_rows(response.json())
        self.assertEqual(rows[0]["__balance__"], -1800)

    def test_client_client_sales_monthly(self):
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("client", "clientsalesmonthlyseries"),
            ),
            data={"client_id": self.client1.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        rows = get_rows(response.json())
        self.assertEqual(rows[0].get("__balance__TS%s0301" % year), 200, rows[0])
        self.assertEqual(rows[0]["__balance__TS%s0201" % year], 100)

        self.assertEqual(rows[0]["__total__TS%s0401" % year], 100)
        self.assertEqual(rows[0]["__total__TS%s0301" % year], 100)
        self.assertEqual(rows[0]["__total__TS%s0201" % year], 100)

        # todo add __fb__ to time series and check the balance

    def test_print(self):
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse("erp_framework:report", args=("client", "balances")),
            data={"print": True},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

    @skip("revise print option with mandatory filters")
    def test_print_header_report(self):
        # todo, printing here is not consistent
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("client", "client_sales_of_products"),
            ),
            data={"print": True},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

    def test_client_statement(self):
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("client", "clientdetailedstatement"),
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

    def test_client_statement_detail(self):
        """
        Test the detail statement
        This is do pass by making a document slug clickable (<a> elem)
        and it also passes by the slug search of the model admin
        :return:
        """
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("client", "clientdetailedstatement"),
            ),
            data={"client_id": self.client1.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        return response

    def test_view_filter(self):
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("client", "clientdetailedstatement"),
            ),
            data={"client_id": self.client1.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        rows = len(get_rows(response.json()))

        without_filter = self.client.get(
            reverse(
                "erp_framework:report",
                args=("client", "clientdetailedstatement"),
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertNotEqual(rows, len(get_rows(without_filter.json())))

    @skip("Feature Halted: No redirect url now")
    def test_report_movement_redirect(self):
        """
        When showing a report, if it contains transactions the slug of the transaction is transformed into an
        <a> elem, here we test that the <a redirect to an actual change form
        :return:
        """
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("client", "clientdetailedstatement"),
            ),
            data={"client_id": self.client1.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        rows = get_rows(response.json())
        a_elem = pq(rows[0]["slug"])
        type = rows[0]["type"]
        url = a_elem.attr("href")
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        instance = response.context["original"]
        self.assertEqual(instance.slug, a_elem.text())
        self.assertEqual(instance.type, type)

    def test_productclientsalesmatrix(self):
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("product", "productclientsalesmatrix"),
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("product", "productclientsalesmatrix"),
            ),
            data={
                # 'matrix_entities': '%s,%s,' % (self.client2.pk, ''),
                "matrix_show_other": True
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

        # todo know why these values are failing and fix them ;_))
        data = response.json()
        # product1_row = get_obj_from_list(data['data'], 'client_id', str(self.product1.pk))
        # print(product1_row)
        # # self.assertEqual(product1_row['__total_MXclient-%s' % self.client1.pk], 300)
        # self.assertEqual(product1_row['__total_MXclient-%s' % self.client2.pk], 600)
        # self.assertEqual(product1_row['__total_MXclient-----'], 900)

        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("product", "productclientsalesmatrix"),
            ),
            data={
                "matrix_entities": [self.client1.pk, self.client2.pk],
                "matrix_show_other": False,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

    # @skip('export to csv ')
    def test_export_to_csv(self):
        self.client.login(username="super", password="secret")

        response = self.client.get(
            reverse("erp_framework:report", args=("product", "total_sales")),
            data={"csv": True, "matrix_show_other": True},
        )
        # HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response)

    def test_default_order_by(self):
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("client", "clienttotalbalancesordered"),
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        rows = get_rows(response.json())
        previous_balance = 0
        self.assertTrue(len(rows) > 1)
        for i, line in enumerate(rows):
            if i == 0:
                previous_balance = line["__balance__"]
            else:
                self.assertTrue(line["__balance__"] > previous_balance)

    @skip("Re Implement oder")
    def test_default_order_by_reversed(self):
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("client", "ClientTotalBalancesOrderedDESC"),
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        rows = get_rows(response.json())
        previous_balance = 0
        self.assertTrue(len(rows) > 1)
        for i, line in enumerate(rows):
            if i == 0:
                previous_balance = line["__balance__"]
            else:
                self.assertTrue(line["__balance__"] < previous_balance)


@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class ReportTest2(BaseTestData, TestCase):
    """
    This is in a class on it's own as for some off reason, while executed as part the other class, it's picked up
    as ajax and redirect is not picked up
    """

    # todo
    @skip("Revise why failing")
    def test_redirect_report_list_when_access_a_report(self):
        """
        Test that accessing a report url directly without ajax return to the report list
        :return:
        """
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("client", "clientdetailedstatement"),
            ),
            data={},
            HTTP_X_REQUESTED_WITH="--",
            follow=False,
        )
        self.assertEqual(response.status_code, 302)


@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class TestAdmin(BaseTestData, TestCase):
    # def test_changelist(self):
    #     self.client.login(username="super", password="secret")
    #     url = Client.get_redirect_url_prefix()
    #     response = self.client.get(url)
    #     self.assertEqual(response.status_code, 200)

    def test_change_form(self):
        self.client.login(username="super", password="secret")
        url = reverse("admin:reporting_tests_client_change", args=(self.client2.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_view(self):
        self.client.login(username="super", password="secret")
        url = reverse("admin:reporting_tests_client_view", args=(self.client2.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_delete_view(self):
        self.client.login(username="super", password="secret")
        url = reverse("admin:reporting_tests_client_delete", args=(self.client2.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_delete_post(self):
        self.client.login(username="super", password="secret")
        url = reverse("admin:reporting_tests_client_delete", args=(self.client2.pk,))
        response = self.client.post(url, data={"post": "yes"})
        self.assertEqual(response.status_code, 302)
        # import pdb; pdb.set_trace()
        self.assertFalse(Client.objects.filter(pk=self.client2.pk).exists())

    def test_history_view(self):
        self.client.login(username="super", password="secret")
        url = reverse("admin:reporting_tests_client_history", args=(self.client2.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # def test_revision_view(self):
    #     self.client.login(username='super', password='secret')
    #     url = reverse('admin:reporting_tests_client_revision', args=(self.client2.pk,))
    #     response = self.client.get(url)
    #     self.assertEqual(response.status_code, 200)

    def test_recoverlist_view(self):
        self.test_delete_post()
        self.client.login(username="super", password="secret")

        url = reverse("admin:reporting_tests_client_recoverlist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # deleted = response.context.get('deleted', False)
        # self.assertTrue(deleted)
        # return deleted

    # def test_recover_view(self):
    #     self.test_delete_post()
    #     self.client.login(username='super', password='secret')
    #
    #     url = reverse('admin:reporting_tests_client_recover', args=(self.client2.pk,))
    #     response = self.client.get(url)
    #     self.assertEqual(response.status_code, 200)

    def test_service_worker(self):
        # self.client.login(username='super', password='secret')

        url = reverse("admin:service-worker")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_manifest(self):
        # self.client.login(username='super', password='secret')

        url = reverse("admin:manifest")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_reset_password_link(self):
        self.client.login(username="super", password="secret")
        url = reverse("erp_framework:auth_user_change", args=(self.user.pk,))
        response = self.client.get(url)
        doc = pq(response.content)
        reset_password_url = doc("a.reset-password").attr("href")
        abs_url = urljoin(url, reset_password_url)
        response = self.client.get(abs_url)
        self.assertEqual(
            response.status_code, 200, "%s %s" % (response.status_code, abs_url)
        )

    def test_add(self):
        self.client.login(username="super", password="secret")
        response = self.client.post(
            reverse("erp_framework:reporting_tests_client_add"),
            data={"slug": 123, "name": "test client %s" % now()},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Client.objects.filter(slug=123).exists())

    def test_app_index(self):
        self.client.login(username="super", password="secret")
        response = self.client.get(
            reverse("erp_framework:app_list", args=("reporting_tests",))
        )
        self.assertEqual(response.status_code, 200)

    def test_my_activity(self):
        self.client.login(username="super", password="secret")
        self.client.post(
            reverse("erp_framework:reporting_tests_client_add"),
            data={"slug": 123, "name": "test client %s" % now()},
        )
        inst = Client.objects.get(slug="123")
        response = self.client.post(
            reverse("erp_framework:reporting_tests_client_change", args=(inst.pk,)),
            data={"slug": 1232, "name": "test client %s" % now()},
        )
        url = reverse("admin:reporting_tests_client_delete", args=(inst.pk,))
        self.client.post(url, data={"post": "yes"})

        response = self.client.get(
            reverse("erp_framework:activity_myactivity_changelist")
        )
        self.assertEqual(response.status_code, 200)

    def test_my_activity_for_non_superuser_is_repeatable(self):
        """A non-superuser hides the user filter; make sure doing so does not
        eat into list_filter permanently (used to raise "pop from empty list")."""
        permission = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(
                MyActivity, for_concrete_model=False
            ),
            codename="view_myactivity",
        )
        self.limited_user.user_permissions.add(permission)
        self.client.login(username="limited", password="password")

        url = reverse("erp_framework:activity_myactivity_changelist")
        for _i in range(3):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.context["cl"].model_admin.get_list_filter(
                    response.wsgi_request
                ),
                [ActionFilter, RAContentTypeFilter],
            )

    @skip
    def test_logentry(self):
        self.client.login(username="super", password="secret")
        response = self.client.get(reverse("erp_framework:admin_logentry_changelist"))
        self.assertEqual(response.status_code, 200)

    def test_login(self):
        response = self.client.get(reverse("erp_framework:login"))
        self.assertEqual(response.status_code, 200)

    @skip
    def test_creation_of_report_permissions(self):
        self.assertTrue(
            self.user.has_perm("reporting_tests.print_productclientsalesmatrix")
        )

        from django.contrib.auth.models import Permission

        self.assertFalse(
            self.limited_user.has_perm("reporting_tests.print_productclientsalesmatrix")
        )
        qs = Permission.objects.filter(codename="print_productclientsalesmatrix")
        self.assertTrue(qs.exists())
        self.limited_user.user_permissions.add(qs[0])

        # reload limited_user so permission can take effect
        limited_user = User.objects.get(username="limited")
        self.assertTrue(
            limited_user.has_perm("reporting_tests.print_productclientsalesmatrix")
        )

    def test_report_access_limited_user_ajax(self):
        self.assertTrue(self.client.login(username="limited", password="password"))
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("product", "productclientsalesmatrix"),
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 403, response)

    def test_report_access_limited_user_direct(self):
        """
        Test the access of a non authorized user
        :return:
        """
        self.assertTrue(self.client.login(username="limited", password="password"))
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("product", "productclientsalesmatrix"),
            )
        )
        self.assertEqual(response.status_code, 403, response)

    def test_report_access_anon_user(self):
        response = self.client.get(
            reverse(
                "erp_framework:report",
                args=("product", "productclientsalesmatrix"),
            )
        )
        self.assertEqual(response.status_code, 302, response)
        self.assertEqual(response.url, reverse("erp_framework:login"))

    def test_save_formset(self):
        self.client.login(username="super", password="secret")
        cash_expense_formsetname = "invoiceline_set"

        on_date = now()

        response = self.client.post(
            reverse("erp_framework:reporting_tests_invoice_add"),
            data={
                "slug": "999",
                "client": self.client1.pk,
                "date": now(),
                "date_1": on_date.strftime("%H:%M"),
                "date_0": on_date.strftime("%Y-%m-%d"),
                "%s-0-product" % cash_expense_formsetname: self.product1.pk,
                "%s-0-quantity" % cash_expense_formsetname: 10,
                "%s-0-price" % cash_expense_formsetname: 10,
                "%s-0-discount" % cash_expense_formsetname: 10,
                "%s-0-value" % cash_expense_formsetname: 10,
                "%s-TOTAL_FORMS" % (cash_expense_formsetname,): 1,
                "%s-INITIAL_FORMS" % (cash_expense_formsetname,): 0,
            },
        )
        # import pdb; pdb.set_trace()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(InvoiceLine.objects.filter(slug=999).exists())

    def test_get_by_slug_view(self):
        self.client.login(username="super", password="secret")
        client = Client.objects.create(name="my name", lastmod_user_id=self.user.pk)
        response = self.client.get(
            reverse("admin:reporting_tests_client_get-by-slug", args=(client.slug,))
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.get(
            reverse("admin:reporting_tests_client_get-by-slug", args=(client.slug,)),
            follow=True,
        )
        # import pdb; pdb.set_trace()
        self.assertEqual(response.context["original"], client)

    # def test_helpcenter_access(self):
    #     self.assertTrue(self.client.login(username='limited', password='password'))
    #     response = self.client.get(reverse('erp_framework:help-center'))
    #     self.assertEqual(response.status_code, 200, response)


@override_settings(ROOT_URLCONF="reporting_tests.urls", USE_TZ=False)
class TestPrePolutaedAdmin(BaseTestData, TestCase):
    """erp_framework.admin.prepopulated.PrepopulatedInlineMixin / HeaderLookupAdminMixin"""

    PREFIX = "journalitem_set"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.journal = Journal.objects.create(
            data="journal 1", lastmod_user=cls.user, date=now(), slug="j1"
        )

    def setUp(self):
        self.client.login(username="super", password="secret")

    def _formset(self, response):
        inline_formsets = response.context["inline_admin_formsets"]
        return inline_formsets[0].formset

    def test_prepopulated_formset_initial(self):
        response = self.client.get(reverse("erp_framework:reporting_tests_journal_add"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Client 1")
        self.assertContains(response, "Client 2")
        self.assertContains(response, "Client 3")

        formset = self._formset(response)
        expected = list(Client.objects.order_by("pk").values_list("pk", flat=True))
        self.assertEqual(len(formset.forms), len(expected))
        self.assertEqual([f.initial["client"] for f in formset.forms], expected)
        # extra data hook
        self.assertEqual(formset.forms[0].initial["data"], f"row-{self.client1.pk}")

    def test_rows_are_locked(self):
        response = self.client.get(reverse("erp_framework:reporting_tests_journal_add"))
        formset = self._formset(response)
        n = len(formset.forms)
        self.assertEqual(formset.min_num, n)
        self.assertEqual(formset.max_num, n)
        self.assertFalse(formset.can_delete)
        self.assertContains(response, f'name="{self.PREFIX}-MAX_NUM_FORMS" value="{n}"')

    def test_entity_rendered_readonly(self):
        response = self.client.get(reverse("erp_framework:reporting_tests_journal_add"))
        self.assertContains(
            response,
            f'<input type="hidden" name="{self.PREFIX}-0-client" value="{self.client1.pk}"',
        )
        self.assertNotContains(response, f'<select name="{self.PREFIX}-0-client"')

    def test_grid_config_and_media(self):
        response = self.client.get(reverse("erp_framework:reporting_tests_journal_add"))
        self.assertContains(response, f'id="{self.PREFIX}-erp-grid"')
        self.assertContains(response, "erp_framework/js/prepopulated_inline.js")
        self.assertContains(response, "erp_framework/vendor/htmx/htmx.min.js")
        formset = self._formset(response)
        self.assertTrue(formset.forms[0].fields["value"].disabled)

    def test_new_addition_in_change(self):
        """
        Test if a new entry in client would be visible in
        an already saved prepopulated formset
        """
        from .models import JournalItem

        JournalItem.objects.create(
            journal=self.journal,
            client=self.client1,
            lastmod_user=self.user,
            date=now(),
            slug="j1",
        )
        Client.objects.create(name="New Client Here", lastmod_user=self.user)

        response = self.client.get(
            reverse("erp_framework:reporting_tests_journal_change", args=(self.journal.pk,))
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Client 1")
        self.assertContains(response, "Client 2")
        self.assertContains(response, "Client 3")
        self.assertContains(response, "New Client Here")

        formset = self._formset(response)
        # 1 saved row + one prepopulated row per remaining client
        total = Client.objects.count()
        self.assertEqual(formset.initial_form_count(), 1)
        self.assertEqual(len(formset.forms), total)
        self.assertEqual(formset.max_num, total)
        clients = [f.initial.get("client") or f.instance.client_id for f in formset.forms]
        self.assertEqual(clients.count(self.client1.pk), 1)

    def test_post_saves_all_prepopulated_rows(self):
        from .models import JournalItem

        data = {
            "slug": "j2",
            "date_0": now().strftime("%Y-%m-%d"),
            "date_1": "10:00:00",
            "data": "journal 2",
            f"{self.PREFIX}-TOTAL_FORMS": "3",
            f"{self.PREFIX}-INITIAL_FORMS": "0",
            f"{self.PREFIX}-MIN_NUM_FORMS": "3",
            f"{self.PREFIX}-MAX_NUM_FORMS": "3",
        }
        for i, c in enumerate([self.client1, self.client2, self.client3]):
            data[f"{self.PREFIX}-{i}-client"] = c.pk
            data[f"{self.PREFIX}-{i}-data"] = "x" if i == 0 else ""
            # computed field: posted value must be ignored
            data[f"{self.PREFIX}-{i}-value"] = "999"
        response = self.client.post(reverse("erp_framework:reporting_tests_journal_add"), data)
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and [
            fs.formset.errors for fs in response.context["inline_admin_formsets"]
        ])
        journal = Journal.objects.get(data="journal 2")
        items = JournalItem.objects.filter(journal=journal)
        self.assertEqual(items.count(), 3)
        self.assertFalse(items.filter(value=999).exists())

    def test_header_lookup_redirects_to_existing(self):
        url = reverse("erp_framework:reporting_tests_journal_header_lookup")
        response = self.client.get(url, {"data": "journal 1", "_object_id": ""})
        self.assertEqual(
            response["HX-Redirect"],
            reverse("erp_framework:reporting_tests_journal_change", args=(self.journal.pk,)),
        )

    def test_header_lookup_reloads_add(self):
        url = reverse("erp_framework:reporting_tests_journal_header_lookup")
        response = self.client.get(url, {"data": "new one", "_object_id": ""})
        self.assertTrue(
            response["HX-Redirect"].startswith(
                reverse("erp_framework:reporting_tests_journal_add") + "?data=new"
            )
        )

    def test_header_lookup_ignores_self_on_change(self):
        url = reverse("erp_framework:reporting_tests_journal_header_lookup")
        response = self.client.get(url, {"data": "journal 1", "_object_id": self.journal.pk})
        self.assertNotIn("HX-Redirect", response)

    def test_header_lookup_attrs_on_form(self):
        response = self.client.get(reverse("erp_framework:reporting_tests_journal_add"))
        self.assertContains(response, 'hx-get="/reporting_tests/journal/header-lookup/"', html=False)


class ReportRegistryTest(TestCase):
    def test_report_registery(self):
        from .reports import ProductClientSales
        from erp_framework.reporting.registry import report_registry
        from erp_framework.reporting.registry import register_report_view

        class ProductClientSales2(ProductClientSales):
            report_slug = "client_sales_of_products_2"

        register_report_view(ProductClientSales2)
        report = report_registry.get("client", "client_sales_of_products_2")
        self.assertIsNotNone(report)

        def get_from_non_existing_admin_site():
            report = report_registry.get(
                "client", "client_sales_of_products_2", admin_site="admin"
            )
            return report

        self.assertRaises(NotRegistered, get_from_non_existing_admin_site)

        register_report_view(ProductClientSales2, admin_site_names=["admin"])
        report = report_registry.get(
            "client", "client_sales_of_products_2", admin_site="admin"
        )
        self.assertIsNotNone(report)

        @register_report_view(admin_site_names=["admin"])
        class ProductClientSales2(ProductClientSales):
            report_slug = "client_sales_of_products_3"

        report = report_registry.get(
            "client", "client_sales_of_products_3", admin_site="admin"
        )
        self.assertIsNotNone(report)

import datetime
from urllib.parse import urljoin

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now
from pyquery import PyQuery as pq

from .models import Client, Product, SimpleSales

User = get_user_model()
SUPER_LOGIN = dict(username='superlogin', password='password')
year = now().year


class ReportRegistryTest(SimpleTestCase):
    pass


class BaseTestData:
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        User.objects.create_superuser('super', None, 'secret')

        user = User.objects.create(is_superuser=True, is_staff=True, **SUPER_LOGIN)
        limited_user = User.objects.create_user(is_superuser=False, is_staff=True, username='limited',
                                                password='password')
        cls.user = user
        cls.limited_user = limited_user
        cls.client1 = Client.objects.create(title='Client 1', lastmod_user=user)
        cls.client2 = Client.objects.create(title='Client 2', lastmod_user=user)
        cls.client3 = Client.objects.create(title='Client 3', lastmod_user=user)

        cls.product1 = Product.objects.create(title='Client 1', lastmod_user=user)
        cls.product2 = Product.objects.create(title='Client 2', lastmod_user=user)
        cls.product3 = Product.objects.create(title='Client 3', lastmod_user=user)

        SimpleSales.objects.create(
            slug=1, doc_date=datetime.datetime(year, 1, 2), client=cls.client1,
            product=cls.product1, quantity=10, price=10, lastmod_user=user)
        SimpleSales.objects.create(
            slug=1, doc_date=datetime.datetime(year, 2, 2), client=cls.client1,
            product=cls.product1, quantity=10, price=10, lastmod_user=user)

        SimpleSales.objects.create(
            slug=1, doc_date=datetime.datetime(year, 3, 2), client=cls.client1,
            product=cls.product1, quantity=10, price=10, lastmod_user=user)

        # client 2
        SimpleSales.objects.create(
            slug=1, doc_date=datetime.datetime(year, 1, 2), client=cls.client2,
            product=cls.product1, quantity=20, price=10, lastmod_user=user)
        SimpleSales.objects.create(
            slug=1, doc_date=datetime.datetime(year, 2, 2), client=cls.client2,
            product=cls.product1, quantity=20, price=10, lastmod_user=user)

        SimpleSales.objects.create(
            slug=1, doc_date=datetime.datetime(year, 3, 2), client=cls.client2,
            product=cls.product1, quantity=20, price=10, lastmod_user=user)

        # client 3
        SimpleSales.objects.create(
            slug=1, doc_date=datetime.datetime(year, 1, 2), client=cls.client3,
            product=cls.product1, quantity=30, price=10, lastmod_user=user)
        SimpleSales.objects.create(
            slug=1, doc_date=datetime.datetime(year, 2, 2), client=cls.client3,
            product=cls.product1, quantity=30, price=10, lastmod_user=user)

        SimpleSales.objects.create(
            slug=1, doc_date=datetime.datetime(year, 3, 2), client=cls.client3,
            product=cls.product1, quantity=30, price=10, lastmod_user=user)


@override_settings(ROOT_URLCONF='reporting_tests.urls', RA_CACHE_REPORTS=True, USE_TZ=False)
class ReportTest(BaseTestData, TestCase):

    def test_client_balance(self):
        self.client.login(username='super', password='secret')
        response = self.client.get(reverse('ra_admin:report', args=('client', 'balances')),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['data'][0]['__balance__'], 300)

    def test_product_total_sales(self):
        self.client.login(username='super', password='secret')
        response = self.client.get(reverse('ra_admin:report', args=('product', 'total_sales')),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['data'][0]['__balance__'], -1800)

    def test_client_client_sales_monthly(self):
        self.client.login(username='super', password='secret')
        response = self.client.get(reverse('ra_admin:report', args=('client', 'clientsalesmonthlyseries')), data={
            'client_id': self.client1.pk
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # self.assertEqual(data['data'][0]['__balance__TS%s0331' % year], 300)
        self.assertEqual(data['data'][0]['__balance__TS%s0228' % year], 200)
        self.assertEqual(data['data'][0]['__balance__TS%s0131' % year], 100)

        self.assertEqual(data['data'][0]['__total__TS%s0331' % year], 100)
        self.assertEqual(data['data'][0]['__total__TS%s0228' % year], 100)
        self.assertEqual(data['data'][0]['__total__TS%s0131' % year], 100)

        # todo add __fb__ to time series and check the balance

    def test_print(self):
        self.client.login(username='super', password='secret')
        response = self.client.get(reverse('ra_admin:report', args=('client', 'balances')),
                                   data={
                                       'print': True
                                   },
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

    def test_print_header_report(self):
        # todo, printing here is not consistent
        self.client.login(username='super', password='secret')
        response = self.client.get(reverse('ra_admin:report', args=('client', 'client_sales_of_products')),
                                   data={
                                       'print': True
                                   },
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

    def test_client_statememnt(self):
        self.client.login(username='super', password='secret')
        response = self.client.get(reverse('ra_admin:report', args=('client', 'clientdetailedstatement')),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

    def test_report_list(self):
        url = Client.get_report_list_url()
        self.client.login(username='super', password='secret')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_productclientsalesmatrix(self):
        self.client.login(username='super', password='secret')
        response = self.client.get(reverse('ra_admin:report', args=('product', 'productclientsalesmatrix')),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('ra_admin:report', args=('product', 'productclientsalesmatrix')),
                                   data={
                                       # 'matrix_entities': '%s,%s,' % (self.client2.pk, ''),
                                       'matrix_show_other': True},
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

        # todo know why these values are failing and fix them ;_))
        data = response.json()
        # product1_row = get_obj_from_list(data['data'], 'client_id', str(self.product1.pk))
        # print(product1_row)
        # # self.assertEqual(product1_row['__total_MXclient-%s' % self.client1.pk], 300)
        # self.assertEqual(product1_row['__total_MXclient-%s' % self.client2.pk], 600)
        # self.assertEqual(product1_row['__total_MXclient-----'], 900)

        response = self.client.get(reverse('ra_admin:report', args=('product', 'productclientsalesmatrix')),
                                   data={'matrix_entities': [self.client1.pk, self.client2.pk],
                                         'matrix_show_other': False},
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

    def test_export_to_csv(self):
        self.client.login(username='super', password='secret')

        response = self.client.get(reverse('ra_admin:report', args=('product', 'productclientsalesmatrix')),
                                   data={
                                       'csv': True,
                                       'matrix_show_other': True}, )
        # HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response)

    def test_default_order_by(self):
        self.client.login(username='super', password='secret')
        response = self.client.get(reverse('ra_admin:report', args=('client', 'clienttotalbalancesordered')),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        previous_balance = 0
        self.assertTrue(len(data['data']) > 1)
        for i, line in enumerate(data['data']):
            if i == 0:
                previous_balance = line['__balance__']
            else:
                self.assertTrue(line['__balance__'] > previous_balance)

    def test_default_order_by_reversed(self):
        self.client.login(username='super', password='secret')
        response = self.client.get(reverse('ra_admin:report', args=('client', 'ClientTotalBalancesOrderedDESC')),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        previous_balance = 0
        self.assertTrue(len(data['data']) > 1)
        for i, line in enumerate(data['data']):
            if i == 0:
                previous_balance = line['__balance__']
            else:
                self.assertTrue(line['__balance__'] < previous_balance)


@override_settings(ROOT_URLCONF='reporting_tests.urls', RA_CACHE_REPORTS=True, USE_TZ=False)
class TestAdmin(BaseTestData, TestCase):

    def test_changelist(self):
        self.client.login(username='super', password='secret')
        url = Client.get_redirect_url_prefix()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_change_form(self):
        self.client.login(username='super', password='secret')
        url = reverse('admin:reporting_tests_client_change', args=(self.client2.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_view(self):
        self.client.login(username='super', password='secret')
        url = reverse('admin:reporting_tests_client_view', args=(self.client2.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_delete_view(self):
        self.client.login(username='super', password='secret')
        url = reverse('admin:reporting_tests_client_delete', args=(self.client2.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_delete_post(self):
        def test_delete_view(self):
            self.client.login(username='super', password='secret')
            url = reverse('admin:reporting_tests_client_delete', args=(self.client2.pk,))
            response = self.client.post(url)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(Client.objects.filter(pk=self.client2.pk).exists())

    def test_history_view(self):
        self.client.login(username='super', password='secret')
        url = reverse('admin:reporting_tests_client_history', args=(self.client2.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # def test_revision_view(self):
    #     self.client.login(username='super', password='secret')
    #     url = reverse('admin:reporting_tests_client_revision', args=(self.client2.pk,))
    #     response = self.client.get(url)
    #     self.assertEqual(response.status_code, 200)

    def test_recoverlist_view(self):
        self.test_delete_post()
        self.client.login(username='super', password='secret')

        url = reverse('admin:reporting_tests_client_recoverlist')
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

        url = reverse('admin:service-worker')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_manifest(self):
        # self.client.login(username='super', password='secret')

        url = reverse('admin:manifest')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_reset_password_link(self):
        self.client.login(username='super', password='secret')
        url = reverse('ra_admin:auth_user_change', args=(self.user.pk,))
        response = self.client.get(url)
        doc = pq(response.content)
        reset_password_url = doc('a.reset-password').attr('href')
        abs_url = urljoin(url, reset_password_url)
        response = self.client.get(abs_url)
        self.assertEqual(response.status_code, 200, "%s %s" % (response.status_code, abs_url))

    def test_add(self):
        self.client.login(username='super', password='secret')
        response = self.client.post(reverse('ra_admin:reporting_tests_client_add'), data={
            'slug': 123,
            'title': 'test client %s' % now(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Client.objects.filter(slug=123).exists())

    def test_app_index(self):
        self.client.login(username='super', password='secret')
        response = self.client.get(reverse('ra_admin:app_list', args=('reporting_tests',)))
        self.assertEqual(response.status_code, 200)
        # self.assertTrue(Client.objects.filter(slug=123).exists())

    def test_login(self):
        response = self.client.get(reverse('ra_admin:login'))
        self.assertEqual(response.status_code, 200)

    def test_creation_of_report_permissions(self):
        self.assertTrue(self.user.has_perm('reporting_tests.print_productclientsalesmatrix'))

        from django.contrib.auth.models import Permission
        self.assertFalse(self.limited_user.has_perm('reporting_tests.print_productclientsalesmatrix'))
        qs = Permission.objects.filter(codename='print_productclientsalesmatrix')
        self.assertTrue(qs.exists())
        self.limited_user.user_permissions.add(qs[0])

        # reload limited_user so permission can take effect
        limited_user = User.objects.get(username='limited')
        self.assertTrue(limited_user.has_perm('reporting_tests.print_productclientsalesmatrix'))

    def test_report_access_limited_user_ajax(self):
        self.assertTrue(self.client.login(username='limited', password='password'))
        response = self.client.get(reverse('ra_admin:report', args=('product', 'productclientsalesmatrix')),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 403, response)

    def test_report_access_limited_user_direct(self):
        self.assertTrue(self.client.login(username='limited', password='password'))
        response = self.client.get(reverse('ra_admin:report', args=('product', 'productclientsalesmatrix')))
        self.assertEqual(response.status_code, 302, response)

    def test_report_access_anon_user(self):
        response = self.client.get(reverse('ra_admin:report', args=('product', 'productclientsalesmatrix')))
        self.assertEqual(response.status_code, 302, response)
        self.assertEqual(response.url, reverse('ra_admin:login'))

    # def test_helpcenter_access(self):
    #     self.assertTrue(self.client.login(username='limited', password='password'))
    #     response = self.client.get(reverse('ra_admin:help-center'))
    #     self.assertEqual(response.status_code, 200, response)

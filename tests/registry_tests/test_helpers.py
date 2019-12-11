from django.test import SimpleTestCase, TestCase, skipUnlessDBFeature

from ra.base.helpers import get_from_list, get_next_serial
from .models import SampleModelA


class TestDocTypeRegistry(SimpleTestCase):
    def test_get_from_list(self):
        l = [
            {'key': 1, 'value': 'one'},
            {'key': 2, 'value': 'two'},
            {'key': 3, 'value': 'three'},
        ]
        output = get_from_list(False, l, 'key', 3)
        self.assertTrue(output == l[2])


class TestHelpers(TestCase):

    def test_get_next_serial(self):
        from django.contrib.auth import get_user_model
        User  = get_user_model()
        self.test_user = User.objects.create_user(username='test', password='test1234', is_staff=True)

        obj = SampleModelA.objects.create(title='Test', lastmod_user=self.test_user, slug='1')
        result2 = get_next_serial(SampleModelA)
        self.assertEqual(int(result2) , int(obj.slug) + 1)

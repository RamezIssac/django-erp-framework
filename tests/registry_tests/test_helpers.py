from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from erp_framework.base.helpers import get_from_list, get_next_serial
from .models import SampleModelA


class TestDocTypeRegistry(SimpleTestCase):
    def test_get_from_list(self):
        l = [
            {"key": 1, "value": "one"},
            {"key": 2, "value": "two"},
            {"key": 3, "value": "three"},
        ]
        output = get_from_list(False, l, "key", 3)
        self.assertTrue(output == l[2])


class TestHelpers(TestCase):
    def test_get_next_serial(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.test_user = User.objects.create_user(
            username="test", password="test1234", is_staff=True
        )

        obj = SampleModelA.objects.create(
            name="Test", lastmod_user=self.test_user, slug="1"
        )
        result2 = get_next_serial(SampleModelA)
        self.assertEqual(int(result2), int(obj.slug) + 1)

    def test_get_next_serial_past_ten(self):
        # Regression: a lexicographic Max on the text slug column ordered
        # "9" > "10" and stalled the counter at 10. The serial must keep
        # counting numerically past 10.
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="test", password="test1234", is_staff=True
        )
        for i in range(1, 11):
            SampleModelA.objects.create(name=f"m{i}", lastmod_user=user, slug=str(i))
        self.assertEqual(int(get_next_serial(SampleModelA)), 11)

    def test_get_next_serial_where_slug_contains_alpha(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.test_user = User.objects.create_user(
            username="test", password="test1234", is_staff=True
        )

        obj = SampleModelA.objects.create(
            name="Test", lastmod_user=self.test_user, slug="A1"
        )
        result2 = get_next_serial(SampleModelA)
        self.assertTrue(result2.isdigit())
        # self.assertEqual(int(result2), int(obj.slug) + 1)


class TestChecks(TestCase):
    @override_settings(
        INSTALLED_APPS=[x for x in settings.INSTALLED_APPS if x != "crequest"],
        MIDDLEWARE=[
            x
            for x in settings.MIDDLEWARE
            if x != "crequest.middleware.CrequestMiddleware"
        ],
    )
    def test_crequest_check(self):
        from erp_framework.checks import check_crequest

        error = check_crequest()
        self.assertIsNotNone(error)
        self.assertEqual(len(error), 2)

    # @override_settings(TEMPLATES[0]['OPTIONS']['context_processors']=[x for x in settings.INSTALLED_APPS if x != 'crequest'],)
    def test_context_processor(self):
        pass

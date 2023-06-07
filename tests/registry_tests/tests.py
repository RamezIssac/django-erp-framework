from unittest import skip

from django.test import SimpleTestCase
from .models import SampleModelA, SampleModelB, ModelWithCustomPK


@skip
class TestDocTypeRegistry(SimpleTestCase):
    # def _test_get_model_doc_type_map(self):
    #     results = SampleModelA.get_doc_type_full_map()
    #     for type in results:
    #         if type["name"] == "transaction":
    #             self.assertTrue("SampleModelA" in type["plus_list"])
    #             self.assertTrue("SampleModelB" in type["minus_list"])

    @skip
    def test_get_doc_type_minus_list(self):
        results = SampleModelB._get_doc_type_minus_list()
        self.assertIn("transaction", results)

    def _test_get_doc_types(self):
        results = SampleModelA.get_doc_types()
        self.assertTrue(type(results) is list)
        self.assertIn("transaction", results)

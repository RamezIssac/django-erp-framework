from django.test import SimpleTestCase
from .models import SampleModelA, SampleModelB, ModelWithCustomPK


class TestDocTypeRegistry(SimpleTestCase):

    def test_get_model_doc_type_map(self):
        results = SampleModelA.get_doc_type_full_map()
        for doc_type in results:
            if doc_type['name'] == 'transaction':
                self.assertTrue('SampleModelA' in doc_type['plus_list'])
                self.assertTrue('SampleModelB' in doc_type['minus_list'])

    def test_get_doc_type_minus_list(self):
        results = SampleModelB.get_doc_type_minus_list()
        self.assertIn('transaction', results)

    def test_get_doc_type_plus_list(self):
        results = SampleModelA.get_doc_type_plus_list()
        self.assertIn('transaction', results)

    def test_get_doc_types(self):
        results = SampleModelA.get_doc_types()
        self.assertTrue(type(results) is list)
        self.assertIn('transaction', results)

    def test_get_pk_name(self):
        self.assertEqual(SampleModelA().get_pk_name(), 'samplemodela_id')
        self.assertEqual(ModelWithCustomPK().get_pk_name(), 'arbitrary_name')



    # def test_get_redirect_url_prefix(self):
    #     results = SampleModelA.get_redirect_url_prefix()

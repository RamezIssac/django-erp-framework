from ra.base.models import BaseInfo
from ra.base.registry import register_doc_type


class SampleModelA(BaseInfo):
    pass


class SampleModelB(BaseInfo):
    pass


doc_type_example = {'name': 'transaction', 'plus_list': ['SampleModelA'], 'minus_list': ['SampleModelB'], }

register_doc_type(doc_type_example)


class ModelWithCustomPK(BaseInfo):
    pk_name = 'arbitrary_name'

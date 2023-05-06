from erp_framework.base.models import EntityModel
from erp_framework.base.registry import register_doc_type


class SampleModelA(EntityModel):
    pass


class SampleModelB(EntityModel):
    pass


doc_type_example = {
    "name": "transaction",
    "plus_list": ["SampleModelA"],
    "minus_list": ["SampleModelB"],
}

register_doc_type(doc_type_example)


class ModelWithCustomPK(EntityModel):
    pk_name = "arbitrary_name"

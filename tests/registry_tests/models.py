from erp_framework.base.models import EntityModel
from erp_framework.doc_types import DocType, doc_type_registry


class SampleModelA(EntityModel):
    pass


class SampleModelB(EntityModel):
    pass


@doc_type_registry.register
class DocTypeExample(DocType):
    name = "transaction"
    plus_list = [SampleModelA]
    minus_list = [SampleModelB]


class ModelWithCustomPK(EntityModel):
    pk_name = "arbitrary_name"

from erp_framework.base.models import EntityModel


class SampleModelA(EntityModel):
    pass


class SampleModelB(EntityModel):
    pass


class ModelWithCustomPK(EntityModel):
    pk_name = "arbitrary_name"

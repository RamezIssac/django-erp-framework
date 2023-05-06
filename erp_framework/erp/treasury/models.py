from erp_framework.base.models import EntityModel
from django.utils.translation import gettext_lazy as _


class Treasury(EntityModel):
    class Meta:
        verbose_name = _("Treasury")
        verbose_name_plural = _("Treasuries")

from ra.base.models import EntityModel
from django.utils.translation import ugettext_lazy as _


class Treasury(EntityModel):
    class Meta:
        verbose_name = _('Treasury')
        verbose_name_plural = _('Treasuries')

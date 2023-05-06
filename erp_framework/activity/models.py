from django.contrib.admin.models import LogEntry
from django.utils.translation import gettext_lazy as _


class MyActivity(LogEntry):
    class Meta:
        proxy = True
        verbose_name = _("My Activity")
        verbose_name_plural = _("My Activities")

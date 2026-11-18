from django.apps import AppConfig

from django.utils.translation import gettext_lazy as _


class ERPFrameworkConfig(AppConfig):
    name = "erp_framework"
    verbose_name = _("ERP Framework")

    def ready(self):
        super().ready()
        from . import checks  # noqa
        from .error_tracking import get_backend

        try:
            backend = get_backend()
        except ImportError:
            return  # reported by the erp_framework.E011 system check
        if backend:
            backend.init_server()

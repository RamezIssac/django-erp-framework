from django.apps import AppConfig

from django.utils.translation import gettext_lazy as _


class ERPFrameworkConfig(AppConfig):
    name = "erp_framework"
    verbose_name = _("ERP Framework")

    def ready(self):
        super().ready()
        from django.db.models.signals import post_migrate, pre_migrate

        from . import checks  # noqa
        from .movements import (
            create_movement_views_after_migrate,
            drop_movement_views_before_migrate,
        )

        pre_migrate.connect(
            drop_movement_views_before_migrate, dispatch_uid="erp_movements_drop"
        )
        post_migrate.connect(
            create_movement_views_after_migrate, dispatch_uid="erp_movements_create"
        )

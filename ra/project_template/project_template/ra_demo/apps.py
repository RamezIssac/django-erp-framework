from django.apps import AppConfig


class RaDemoConfig(AppConfig):
    name = 'ra_demo'

    def ready(self):
        super().ready()
        from . import reports

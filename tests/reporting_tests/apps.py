from django import apps


class ReportTestApp(apps.AppConfig):
    name = 'reporting_tests'

    def ready(self):
        from .reports import ClientTotalBalance

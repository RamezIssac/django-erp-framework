from __future__ import unicode_literals


def register_report_view(report_class=None, condition=None):
    from .registry import report_registry

    if report_class:
        report_registry.register(report_class)
        return report_class

    def wrapper(report_class):
        if callable(condition):
            if not condition():
                return report_class
        report_registry.register(report_class)
        return report_class

    return wrapper

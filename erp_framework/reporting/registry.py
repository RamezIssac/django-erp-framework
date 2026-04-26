from collections import OrderedDict
from functools import wraps
from inspect import getfullargspec, unwrap

from django.contrib.admin.sites import AlreadyRegistered, NotRegistered
from django.core.exceptions import ImproperlyConfigured

from erp_framework.base import app_settings



class ReportRegistry(object):
    def __init__(self):
        super(ReportRegistry, self).__init__()
        self._registry = OrderedDict()
        self._slugs_registry = []
        self._store = OrderedDict()
        self._base_models = []

    def register(self, func=None, erp_admin_sites_names=None):
        """
        Register a callable as a compiled template tag. Example:

        @register.simple_tag
        def hello(*args, **kwargs):
            return 'world'
        """

        def dec(func):
            (
                params,
                varargs,
                varkw,
                defaults,
                kwonly,
                kwonly_defaults,
                _,
            ) = getfullargspec(unwrap(func))

            self._register(func, erp_admin_sites_names)
            return func

        if func is None:
            # @register.simple_tag(...)
            return dec
        elif callable(func):
            # @register.simple_tag
            return dec(func)
        else:
            raise ValueError("Invalid arguments provided to register")

    def _register(self, report_class, erp_admin_sites_names=None):
        """
        Register report class
        :param report_class:
        :return:
        """
        erp_admin_sites_names = erp_admin_sites_names or [
            app_settings.ERP_FRAMEWORK_SITE_NAME
        ]

        if not getattr(report_class, "hidden", False):
            namespace = report_class.get_base_model_name()
            try:
                if not report_class.report_title:
                    raise AttributeError
            except AttributeError:
                raise ImproperlyConfigured(
                    "Report %s is missing a `report_title`" % report_class
                )
            # try:
            #     assert type(report_class.form_settings) is dict
            # except (AttributeError, AssertionError):
            #     raise ImproperlyConfigured(
            #         'Report %s is missing a `form_settings` or form_settings is not a dict' % report_class)
            if not report_class.get_report_model():
                raise ImproperlyConfigured(
                    "Report %s is missing a `report_model`" % report_class
                )
            # if report_class.must_exist_filter and not report_class.header_report:
            #     raise ImproperlyConfigured('%s: Must specify a view class or function in `header_report` '
            #                                'if `must_exist_filter` is set' % report_class)

            self._register_report(report_class, namespace, erp_admin_sites_names)

    def _register_report(self, report, namespace, erp_admin_sites_names):
        """
        Actual registry function, recursive
        :param report:
        :param namespace:
        :return:
        """

        for admin_site in erp_admin_sites_names:
            full_name = f"{namespace}.{report.get_report_slug()}"
            base_model = report.get_base_model_name()
            self._registry.setdefault(admin_site, OrderedDict())
            self._registry[admin_site].setdefault(base_model, [])
            self._registry[admin_site][base_model].append(report)
            self._store.setdefault(admin_site, OrderedDict())
            if report.base_model not in self._base_models:
                self._base_models.append(report.base_model)
            self._slugs_registry.append(full_name)
            self._store[admin_site][full_name] = report

    def unregister(self, report_class, w_other_namespaces=True):
        self._unregister(report_class, report_class.namespace)
        if w_other_namespaces:
            other_namespaces = report_class.other_namespaces or []
            for e in other_namespaces:
                self._unregister(report_class, e)

    def unregister_namespace(self, namespace):
        reports = self._registry.pop(namespace, [])
        for r in reports:
            slug_id = "%s.%s" % (namespace, r.get_reprot_slug())
            self._store.pop(slug_id)
        return reports

    def _unregister(self, report_class, namespace):
        if type(self._registry[namespace]) is list:
            if report_class not in self._registry[namespace]:
                raise NotRegistered("This report is not registered")
            self._registry[namespace].remove(report_class)
            self._base_models.remove(report_class.base_model)

    # def get_report_classes_by_namespace(self, namespace):
    #     if namespace in self._registry:
    #         return self._registry[namespace]
    #     return []
    # else:
    #     raise NotRegistered(namespace)

    def get_all_reports(self, admin_site=None, all_sites=False):
        reports = []
        if not admin_site and not all_sites:
            return []
        # admin_site = admin_site or app_settings.ERP_FRAMEWORK_SITE_NAME
        if all_sites:
            admin_sites = self._registry.keys()
        else:
            admin_sites = [admin_site]

        for admin_site in admin_sites:
            registry = self._registry.get(admin_site, {})
            for namespace in registry:
                reports += list(registry[namespace])
        return list(OrderedDict.fromkeys(reports))

    def get(self, namespace, report_slug, admin_site=None):
        admin_site = admin_site or app_settings.ERP_FRAMEWORK_SITE_NAME

        slug_id = "%s.%s" % (namespace, report_slug)
        try:
            return self._store[admin_site][slug_id.lower()]
        except KeyError:
            raise NotRegistered(
                "Report %s.%s is not found, Did you register it? If yes, then maybe it's has different namespace ? Options are: %s"
                % (
                    namespace,
                    report_slug,
                    ",".join(self._store.get(admin_site, {}).keys()),
                )
            )

    def get_base_models(self):
        return self._base_models

    def get_base_models_with_reports(self, admin_site):
        output = []
        registry = self._registry.get(admin_site, {})
        for k, v in registry.items():
            bm = v[0].base_model if v else None
            output.append((bm._meta if bm else k, v))
        return output


report_registry = ReportRegistry()


def register_report_view(report_class=None, admin_site_names="", condition=None):
    admin_site_names = admin_site_names or [app_settings.ERP_FRAMEWORK_SITE_NAME]
    # check if admin_site_names is a str
    if type(admin_site_names) is str:
        admin_site_names = [admin_site_names]

    if report_class:
        report_registry.register(report_class, admin_site_names)
        return report_class

    def wrapper(report_class):
        if callable(condition):
            if not condition():
                return report_class
        report_registry.register(report_class, admin_site_names)
        return report_class

    return wrapper

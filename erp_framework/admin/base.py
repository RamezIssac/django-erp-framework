from __future__ import unicode_literals

import logging
from functools import update_wrapper

from django.apps import apps
from django.contrib.admin import AdminSite
from django.http import JsonResponse
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.urls import re_path as url, include
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _

from erp_framework.admin.helpers import get_each_context
from erp_framework.base import app_settings
from erp_framework.base.helpers import get_from_list

# from erp_framework.top_search.views import TopSearchView

logger = logging.getLogger(__name__)
CACHE_DURATION = 0

MSG_ADDED_SUCCESSFULLY = _('The %(name)s "%(obj)s" was added successfully.')
MSG_CHANGED_SUCCESSFULLY = _('The %(name)s "%(obj)s" was changed successfully.')
MSG_YOU_MAY_ADD = _("You may add another %(name)s below")
MSG_YOU_MAY_CHANGE = _("You may change it again below.")


def get_report_list_class(request, base_model):
    from erp_framework.base.app_settings import RA_REPORT_LIST_MAP
    from erp_framework.reporting.views import ReportList

    klass = RA_REPORT_LIST_MAP.get(base_model, False)
    if klass:
        klass = import_string(klass)
        if callable(klass):
            return klass(request, base_model=base_model)
    else:
        klass = ReportList

    return klass.as_view()(request, base_model=base_model)


def get_report_view(request, base_model, report_slug):
    from erp_framework.reporting.registry import report_registry

    klass = report_registry.get(base_model, report_slug)
    return klass.as_view()(request)


class RaAdminSiteBase(AdminSite):
    site_title = app_settings.ERP_ADMIN_SITE_TITLE
    site_header = app_settings.ERP_ADMIN_SITE_HEADER
    index_title = app_settings.ERP_ADMIN_INDEX_TITLE

    index_template = app_settings.ERP_ADMIN_INDEX_TEMPLATE
    app_index_template = app_settings.RA_ADMIN_APP_INDEX_TEMPLATE
    login_template = app_settings.RA_ADMIN_LOGIN_TEMPLATE

    # logout_template = app_settings.RA_ADMIN_LOGGED_OUT_TEMPLATE

    def get_urls(self):
        # from erp_framework.utils.views import access_denied
        def wrap(view, cacheable=False):
            def wrapper(*args, **kwargs):
                return self.admin_view(view, cacheable)(*args, **kwargs)

            return update_wrapper(wrapper, view)

        urls = super(RaAdminSiteBase, self).get_urls()
        help_center = [
            url(r"^i18n/", include("django.conf.urls.i18n")),
        ]

        settings_update = [
            url(r"^manifest/$", self.manifest_view, name="manifest"),
            url(r"^sw.js$", self.service_worker_view, name="service-worker"),
        ]

        urlpatterns = [
            url(
                r"^reports/(?P<base_model>[\w-]+)/$",
                get_report_list_class,
                name="report_list",
            ),
            url(
                r"^reports/(?P<base_model>[\w-]+)/(?P<report_slug>[\w-]+)/$",
                get_report_view,
                name="report",
            ),
            # new from sites
            # path('top-search/', TopSearchView.as_view(), name='top-search'),
            # path('access-denied/', access_denied, name='access-denied'),
        ]

        return help_center + settings_update + urlpatterns + urls

    def service_worker_view(self, request):
        return render(
            request,
            f"erp_framework/service-worker.js.html",
            content_type="application/javascript",
        )

    def manifest_view(self, request):
        json = {
            "short_name": "ERP Framework System",
            "name": "ERP Framework System",
            "icons": [
                {
                    "src": "/static/ra/images/ra_systems.png",
                    "type": "image/png",
                    "sizes": "147x147",
                },
                # {
                #     "src": "launcher-icon-2x.png",
                #     "type": "image/png",
                #     "sizes": "96x96"
                # },
                # {
                #     "src": "launcher-icon-4x.png",
                #     "type": "image/png",
                #     "sizes": "192x192"
                # }
            ],
            "start_url": "../?launcher=true",
            "display": "standalone",
            "theme_color": "#000066",
            "background_color": "#fff",
        }
        return JsonResponse(json, status=200)

    def __init__(self, name="admin"):
        super(RaAdminSiteBase, self).__init__(name)

        self._registry_names = {}  # holds model name -> ModelAdmin instances
        #                  l-> Model
        self._registered_models_CT = []

    def _fill_registry_names(self):
        """
        Fills the `self._registry_names`
        """
        for model in self._registry.keys():
            try:
                model_name = model.get_class_name().lower()
            except AttributeError:
                model_name = model._meta.model_name.lower()
            self._registry_names[model_name] = {
                "admin": self._registry[model],
                "model": model,
            }

    def app_index(self, request, app_label, extra_context=None):
        app_name = apps.get_app_config(app_label).verbose_name
        context = self.each_context(request)
        app_list = context["app_list"]
        current_app_list = get_from_list(False, app_list, "app_label", app_label)
        context.update(
            dict(
                title=_("%(app)s administration") % {"app": app_name},
                # current_app_list=[app_dict],
                current_app_list=[current_app_list],
                app_label=app_label,
                app_name=app_name,
            )
        )
        context.update(extra_context or {})
        request.current_app = self.name

        return TemplateResponse(
            request,
            self.app_index_template
            or ["admin/%s/app_index.html" % app_label, "admin/app_index.html"],
            context,
        )

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["opts"] = {"app_name": "home"}
        extra_context["is_index"] = True
        extra_context["sidebar_status"] = "expanded"
        context = dict(
            self.each_context(request),
            name=self.index_title,
        )
        context.update(extra_context or {})

        request.current_app = self.name
        context["title"] = app_settings.ERP_ADMIN_INDEX_TITLE

        return TemplateResponse(
            request, self.index_template or "admin/index.html", context
        )

    def each_context(self, request):
        context = super(RaAdminSiteBase, self).each_context(request)
        context["RA_ADMIN_SITE_NAME"] = app_settings.RA_ADMIN_SITE_NAME
        context.update(get_each_context(request, self))
        return context

    def get_admin_by_model_name(self, model_name):
        """
        Get the model admin of a model by its name
        :param model_name:
        :return: ModalAdmin Instance or None
        """
        if not self._registry_names:
            self._fill_registry_names()
        return self._registry_names.get(model_name, None)

    def login(self, request, extra_context=None):
        extra_context = extra_context or {}
        # extra_context["SHOW_LANGUAGE_SELECTOR"] = True
        return super(RaAdminSiteBase, self).login(request, extra_context)

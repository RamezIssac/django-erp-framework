import copy
import hashlib
import logging

import simplejson as json
from django.conf import settings
from django.contrib.auth.mixins import AccessMixin, UserPassesTestMixin
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.template.defaultfilters import capfirst
from django.urls import reverse, reverse_lazy
from django.utils.translation import get_language_bidi, gettext
from django.views.generic import TemplateView

from erp_framework.base import app_settings, registry
from erp_framework.base.app_settings import RA_ADMIN_SITE_NAME
from erp_framework.base.helpers import dictsort
from erp_framework.reporting.forms import OrderByForm
from erp_framework.reporting.printing import (
    regroup_data,
    HTMLPrintingClass,
    ExportToCSV,
)
from slick_reporting.form_factory import report_form_factory
from slick_reporting.generator import ReportGenerator
from slick_reporting.views import SlickReportViewBase

# from .generator import ReportGenerator
# from .meta_data import ReportMetaData

logger = logging.getLogger("erp_framework.reporting")


class RaMultiplePermissionsRequiredMixin(AccessMixin):
    """
    View mixin which allows you to specify two types of permission
    requirements. The `permissions` attribute must be a dict which
    specifies two keys, `all` and `any`. You can use either one on
    its own or combine them. The value of each key is required to be a
    list or tuple of permissions. The standard Django permissions
    style is not strictly enforced. If you have created your own
    permissions in a different format, they should still work.

    By specifying the `all` key, the user must have all of
    the permissions in the passed in list.

    By specifying The `any` key , the user must have ONE of the set
    permissions in the list.

    Class Settings
        `permissions` - This is required to be a dict with one or both
            keys of `all` and/or `any` containing a list or tuple of
            permissions.
        `login_url` - the login url of site
        `redirect_field_name` - defaults to "next"
        `raise_exception` - defaults to False - raise 403 if set to True

    Example Usage
        class SomeView(MultiplePermissionsRequiredMixin, ListView):
            ...
            #required
            permissions = {
                "all": ("blog.add_post", "blog.change_post"),
                "any": ("blog.delete_post", "user.change_user")
            }

            #optional
            login_url = "/signup/"
            redirect_field_name = "hollaback"
            raise_exception = True
    """

    permissions = None  # Default required perms to none
    permission_or_test = False
    login_url = reverse_lazy("%s:login" % RA_ADMIN_SITE_NAME)
    _bypass = False

    def get_or_test(self):
        return False

    def get_permissions(self):
        return self.permissions

    def return_access_denied(self):
        raise PermissionDenied
        # return HttpResponseForbidden()
        # return HttpResponseRedirect(reverse('access_denied'))

    def dispatch(self, request, *args, **kwargs):
        from django.contrib.auth.views import redirect_to_login

        if request.user.is_anonymous:
            return redirect_to_login(
                request.get_full_path(),
                self.get_login_url(),
                self.get_redirect_field_name(),
            )

        self._check_permissions_attr()

        perms_all = self.get_permissions().get("all") or None
        perms_any = self.get_permissions().get("any") or None

        self._check_permissions_keys_set(perms_all, perms_any)
        self._check_perms_keys("all", perms_all)
        self._check_perms_keys("any", perms_any)

        # If perms_all, check that user has all permissions in the list/tuple
        if perms_all:
            if not request.user.has_perms(perms_all):
                if not (self.permission_or_test and self.get_or_test()):
                    # if self.raise_exception:
                    raise PermissionDenied
                    # return access_denied

        # If perms_any, check that user has at least one in the list/tuple
        if perms_any:
            has_one_perm = False
            for perm in perms_any:
                if request.user.has_perm(perm):
                    has_one_perm = True
                    break

            if not has_one_perm:
                raise PermissionDenied

        return super(RaMultiplePermissionsRequiredMixin, self).dispatch(
            request, *args, **kwargs
        )

    def _check_permissions_attr(self):
        """
        Check permissions attribute is set and that it is a dict.
        """
        permissions = self.get_permissions()
        if permissions is None or not isinstance(permissions, dict):
            raise ImproperlyConfigured(
                "'PermissionsRequiredMixin' requires "
                "'permissions' attribute to be set to a dict."
            )

    def _check_permissions_keys_set(self, perms_all=None, perms_any=None):
        """
        Check to make sure the keys `any` or `all` are not both blank.
        If both are blank either an empty dict came in or the wrong keys
        came in. Both are invalid and should raise an exception.
        """
        if perms_all is None and perms_any is None and not self._bypass:
            raise ImproperlyConfigured(
                "'PermissionsRequiredMixin' requires"
                "'permissions' attribute to be set to a dict and the 'any' "
                "or 'all' key to be set."
            )

    def _check_perms_keys(self, key=None, perms=None):
        """
        If the permissions list/tuple passed in is set, check to make
        sure that it is of the type list or tuple.
        """
        if perms and not isinstance(perms, (list, tuple)):
            raise ImproperlyConfigured(
                "'MultiplePermissionsRequiredMixin' "
                "requires permissions dict '%s' value to be a list "
                "or tuple." % key
            )


class ReportListBase(RaMultiplePermissionsRequiredMixin, TemplateView):
    """
    Base class to create a report list page
    """

    def get_meta_data(self):
        """
        Gets Meta data used for Page title , breadcrumbs links etc.
        Make sure that opts is a model._meta or s sufficient dictionary
        :return: tuple (verbose_name, verbose_name_plural, page_title, model_meta)
        """
        raise NotImplemented

    def get_permissions(self):
        """
        Override of RAAccessControl.get_permissions
        :return: a dictionary with 'any' and/ or 'all' permission. required
        """
        raise NotImplemented

    def get_reports_map(self):
        """
        Hook to get reports. By default it uses the helper `get_reports_map` to get
         the reports based on the base_model, However you can override and return your list of reports

        :return: a dictionary with two values `slugs` and `reports`
        slugs: map to a list of report slugs
        reports: map to a list of ReportView classes
        """
        raise NotImplemented


class ReportList(ReportListBase):
    template_name = f"erp_framework/report_list.html"
    _bypass = True

    def get_order_list(self):
        from erp_framework.admin.admin import erp_admin_site

        model_admin = erp_admin_site.get_admin_by_model_name(self.kwargs["base_model"])
        if model_admin:
            try:
                return model_admin["admin"].typed_reports_order_list or []
            except AttributeError:
                # The admin class does not have an order list for teh reports
                pass
        return []

    def get_permissions(self):
        return {}

    def get_reports_map(self):
        from erp_framework.admin.admin import get_reports_map
        from erp_framework.base.registry import get_ra_model_by_name

        model = get_ra_model_by_name(self.kwargs["base_model"])
        try:
            model_name = model.get_class_name().lower()
        except:
            model_name = model._meta.model_name
        val = get_reports_map(
            model_name, self.request.user, self.request, self.get_order_list()
        )
        return val

    def get_meta_data(self):
        model = registry.get_ra_model_by_name(self.kwargs["base_model"])
        verbose_name = model._meta.verbose_name
        verbose_name_plural = model._meta.verbose_name_plural
        is_bidi = get_language_bidi()
        if is_bidi:
            page_title = "%s %s" % (gettext("reports"), model._meta.verbose_name_plural)
        else:
            page_title = "%s %s" % (model._meta.verbose_name_plural, gettext("reports"))
        opts = model._meta
        return verbose_name, verbose_name_plural, page_title, opts

    def get_context_data(self, **kwargs):
        from erp_framework.admin.admin import erp_admin_site

        context = super(ReportList, self).get_context_data(**kwargs)

        context["reports"] = self.get_reports_map()

        v, vp, page_title, opts = self.get_meta_data()
        context["verbose_name"] = v
        context["verbose_name_plural"] = vp
        context["page_title"] = page_title
        context["title"] = page_title

        context["opts"] = opts

        context["RA_ADMIN_SITE_NAME"] = app_settings.RA_ADMIN_SITE_NAME
        context["has_detached_sidebar"] = True
        context["RA_ADMIN_SITE_NAME"] = app_settings.RA_ADMIN_SITE_NAME
        context["is_report"] = True
        context["base_model"] = self.kwargs["base_model"].lower()
        context["report_slug"] = ""

        extra_context = erp_admin_site.each_context(self.request)
        context.update(extra_context)
        return context


class ReportView(UserPassesTestMixin, SlickReportViewBase):
    """
    The Base class for reports .
    It handles the report ajax request, load the report form which provides the needed filers,
    Load the report generator class , csv_export_class and the printing class.

    """

    # class responsible for generating the report, applying the filter and computing
    report_generator_class = ReportGenerator

    # class responsible for supplying meta data for front end
    # report_meta_data_class = ReportMetaData

    # class responsible for customizing the output for print
    printing_class = HTMLPrintingClass

    # required. the model which holds the data
    report_model = None

    # required , the main model which the report is about.
    # We will be getting the doc_types (if any) from this model and be basing the calculation on.
    base_model = None

    # the report form, A subclass of ReportForm is to expected
    form_class = None

    # control the chart settings, passed to front end as is.
    chart_settings = None

    other_namespaces = None
    columns = None

    report_slug = ""
    page_title = None
    report_title = ""
    date_field = "date"
    # default order by for the results.
    # ordering can also be controlled on run time by passing order_by='field_name'
    # For DESC order supply order_by='-field_name'
    default_order_by = None

    # this report will not be visible on the menu or accessed on its own
    hidden = False

    # will swap the sign on the report, useful when reporting on object which main side is credit

    # Control the header report function
    must_exist_filter = None
    header_report = None

    # to limit records not to exceed certain number, useful for very large reports
    limit_records = False

    perform_regroup_when_print = False  # Handling printing header & sub data

    # size for printing , useful on very large data
    print_buffer = 10000

    # control the caching
    cache = True
    cache_duration = 300
    with_type = True

    admin_site_name = "erp_admin"
    template_name = "erp_framework/report.html"

    def get_context_data(self, **kwargs):
        from erp_framework.admin.admin import erp_admin_site

        context = super().get_context_data(**kwargs)
        extra_context = erp_admin_site.each_context(self.request)
        context.update(extra_context)
        context["is_report"] = True
        context["current_base_model_name"] = self.base_model.__name__.lower()
        context["base_model"] = self.base_model
        context["report_slug"] = self.get_report_slug()
        context["report"] = self

        return context

    def get_doc_types_q_filters(self):
        return [], []

        # doc_types = registry.get_model_doc_type_map(self.base_model.__name__)
        # return [Q(type__in=doc_types['plus_list'])], [Q(type__in=doc_types['minus_list'])]

    def get_report_generator(self, queryset, for_print):
        q_filters, kw_filters = self.form.get_filters()
        if self.crosstab_model:
            self.crosstab_ids = self.form.get_crosstab_ids()

        crosstab_compute_reminder = (
            self.form.get_crosstab_compute_reminder()
            if self.request.GET or self.request.POST
            else self.crosstab_compute_reminder
        )
        doc_type_plus_list, doc_type_minus_list = [], []

        if self.with_type:
            doc_type_plus_list, doc_type_minus_list = self.get_doc_types_q_filters()

        time_series_pattern = self.time_series_pattern
        if self.time_series_selector:
            time_series_pattern = self.form.cleaned_data["time_series_pattern"]

        return self.report_generator_class(
            self.get_report_model(),
            start_date=self.form.cleaned_data["start_date"],
            end_date=self.form.cleaned_data["end_date"],
            q_filters=q_filters,
            kwargs_filters=kw_filters,
            date_field=self.date_field,
            main_queryset=queryset,
            print_flag=for_print,
            limit_records=self.limit_records,
            swap_sign=self.swap_sign,
            columns=self.columns,
            group_by=self.group_by,
            time_series_pattern=time_series_pattern,
            time_series_columns=self.time_series_columns,
            crosstab_model=self.crosstab_model,
            crosstab_ids=self.crosstab_ids,
            crosstab_columns=self.crosstab_columns,
            crosstab_compute_reminder=crosstab_compute_reminder,
            format_row_func=self.format_row,
            doc_type_plus_list=doc_type_plus_list,
            doc_type_minus_list=doc_type_minus_list,
        )

    @classmethod
    def get_report_slug(cls):
        return cls.report_slug or cls.__name__.lower()

    @classmethod
    def get_base_model_name(cls):
        """
        A convenience method to get the base model name
        :return:
        """
        return cls.base_model._meta.model_name

    @classmethod
    def get_url(cls):
        url = reverse(
            f"{RA_ADMIN_SITE_NAME}:report_list", args=(cls.get_base_model_name(),)
        )
        url += "%s/" % cls.get_report_slug()
        return url

    def test_func(self):
        app_label = self.base_model._meta.app_label
        codename = f"view_{self.get_report_slug()}"
        return self.request.user.has_perm(f"{app_label}.{codename}")

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            if self.request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
                return JsonResponse({}, status=403)
            else:
                raise PermissionDenied
            #     return HttpResponseRedirect(reverse('erp_admin::access-denied'))
        # else:
        return HttpResponseRedirect(reverse("erp_admin:login"))

    @classmethod
    def get_absolute_url(self):
        return reverse(
            "admin:report",
            args=(self.base_model._meta.model_name, self.get_report_slug()),
            current_app=self.admin_site_name,
        )

    @classmethod
    def get_report_model(cls):
        """
        Problem: During tests, override settings is used, making the report model always returning the model
        'first to be found' not the potentially swapped one ,raising an error. so , it is advised to use this method instead
            of declaring the report model on the module level.
        :return: the Model to use
        """
        return cls.report_model

    @staticmethod
    def form_filter_func(fkeys_dict):
        output = {}
        for k, v in fkeys_dict.items():
            if k not in ["owner_id", "polymorphic_ctype_id", "lastmod_user_id"]:
                output[k] = v
        return output

    @classmethod
    def get_form_class(cls):
        """
        As Report Model might be swapped, form_class cant be accurately generated on model load,
        hence this function.
        :return: form_class
        """
        return cls.form_class or report_form_factory(
            cls.get_report_model(),
            crosstab_model=cls.crosstab_model,
            display_compute_reminder=cls.crosstab_compute_reminder,
            fkeys_filter_func=cls.form_filter_func,
            initial=cls.get_form_initial(),
            show_time_series_selector=cls.time_series_selector,
            time_series_selector_choices=cls.time_series_selector_choices,
            time_series_selector_default=cls.time_series_selector_default,
            time_series_selector_allow_empty=cls.time_series_selector_allow_empty,
        )

    def dispatch(self, request, *args, **kwargs):
        report_slug = kwargs.get("report_slug", False)
        if report_slug:
            self.report_slug = report_slug
        val = super(ReportView, self).dispatch(request, *args, **kwargs)

        return val

    def get_printing_class(
        self,
    ):
        return self.printing_class

    def is_print_request(self):
        return self.request.GET.get("print", False)

    @classmethod
    def get_initialized_form(cls):
        """
        Get the form_class initialized.
        :return:
        """
        form_class = cls.get_form_class()
        return form_class()

    @classmethod
    def get_all_print_settings(cls):
        # todo review
        return {}

    def return_header_report_or_none(self):
        """
        Check if we need to return o
        :return:
        """

        if self.must_exist_filter:
            filter_exist = self.request.GET.get(self.must_exist_filter, "")
            # if the filter exists but the the user choose several entities
            filter_exist = filter_exist.find(",") == -1 and bool(filter_exist)
            if not filter_exist:
                return JsonResponse({}, status=204)
                return self.header_report.as_view()(
                    self.request,
                    original_report_slug=self.get_report_slug(),
                    as_header=True,
                )
        return None

    def get_print_response(self, response, header_report, must_exist_filter):
        """
        Invoke the printing class and return the printing response
        :return:  Response
        """

        if must_exist_filter and header_report:
            if self.perform_regroup_when_print:
                response["sub_data"] = regroup_data(
                    response["data"], header_report, must_exist_filter
                )
                response["header_group"] = header_report
            else:
                _available_buffer = self.print_buffer
                must_exist_filter = must_exist_filter.replace("__slug", "_id")
                response["sub_data"] = {}
                json_data = json.loads(header_report.content)
                response["header_data"] = []
                response["header_group"] = must_exist_filter

                for line in json_data["data"]:
                    pivot_id = line[must_exist_filter]
                    new_request = copy.copy(self.request)
                    get_data = new_request.GET.copy()
                    get_data[must_exist_filter] = pivot_id
                    get_data["print_recursive"] = True
                    get_data["get_group"] = False
                    new_request.GET = get_data
                    pivot_report = self.__class__.as_view()(new_request)
                    data_check = pivot_report.get("data", [])
                    if not len(data_check) > 0:
                        _available_buffer -= len(pivot_report.get("data", []))
                        response["sub_data"][pivot_id] = pivot_report
                        response["header_data"].append(line)
                        if _available_buffer < 0:
                            break

        return self.get_printing_class()(
            self.request,
            self.form_settings or {},
            response,
            header_report,
            must_exist_filter,
            self,
        ).get_response()

    # todo delete
    def cache_and_return(self, results):
        return results
        status, key = self.get_cache_status_and_key(self.request)
        if key:
            cache.set(key, results, self.cache_duration)
        return results

    def cache_view(self):
        return self.cache and app_settings.RA_CACHE_REPORTS

    def get_cache_status_and_key(self, request):
        if not self.cache or not app_settings.RA_CACHE_REPORTS:
            return False, None

        url = request.get_full_path()
        url_parts = url.split("&")
        url_parts = [x for x in url_parts if not x.startswith("csrf")]
        no_cache_request = "no-cache" in url_parts
        if no_cache_request:
            url_parts.remove("no-cache")
        url = "".join(url_parts)
        m = hashlib.md5()
        if app_settings.RA_CACHE_REPORTS_PER_USER:
            m.update(f"{request.user.pk}".encode("utf-8"))
        m.update(url.encode("utf-8"))
        cache_key = m.hexdigest()
        return not no_cache_request, cache_key

    def get_export_response(self, response, header_report, must_exist_filter):
        return self.csv_export_class(
            self.request,
            self.form_settings or {},
            response,
            header_report,
            must_exist_filter,
            self,
        ).get_response()

    def _get(self, request, *args, **kwargs):
        cache_status, cache_key = self.get_cache_status_and_key(request)
        if cache_status and cache_key:
            cache_val = cache.get(cache_key)
            if cache_val:
                return cache_val

        # self.parse()

        form_class = self.get_form_class()
        self.form = self.get_form(form_class)
        enable_print = self.is_print_request()
        export_csv = request.GET.get("csv", False)

        # if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or enable_print or export_csv or (
        #         request.GET.get('ajax') == 'true' and settings.DEBUG):
        if request.GET and self.form.is_valid():
            must_exist_filter = self.must_exist_filter or ""
            must_exist_filter = must_exist_filter.replace("_id", "__slug")
            header_report = self.return_header_report_or_none()
            # Case of a report that needs a specific filter to run,
            # in case it doesn't exist, we return the `header_report`
            if header_report and not enable_print:
                return self.cache_and_return(header_report)
            as_header = self.kwargs.get("as_header", False)

            response = self.get_report_results(enable_print or export_csv)

            if (export_csv or enable_print) and not as_header:
                response = self.prepare_results_for_printing(response)
                if export_csv:
                    return self.get_export_response(
                        response, header_report, must_exist_filter
                    )

                return self.get_print_response(
                    response, header_report, must_exist_filter
                )
            return self.cache_and_return(
                HttpResponse(
                    self.serialize_to_json(response), content_type="application/json"
                )
            )
        else:
            return self.form_invalid(self.form)
        # else:
        #     # Accessing the report page directly is not allowed
        #     return HttpResponseRedirect(
        #         reverse(f'{RA_ADMIN_SITE_NAME}:report_list', args=(self.get_base_model_name(),)))

    @classmethod
    def get_report_title(cls):
        """
        :return: The report name
        """
        # name = 'name'
        name = ""
        if cls.report_title:
            name = cls.report_title
        elif cls.page_title:
            name = cls.page_title
        return capfirst(name)

    def get_metadata(self, generator):
        metadata = super().get_metadata(generator)
        metadata["report_title"] = self.report_title
        return metadata

    def order_results(self, data):
        """
        order the results based on GET parameter or default_order_by
        :param data: List of Dict to be ordered
        :return: Ordered data
        """
        order_field, asc = OrderByForm(self.request.GET).get_order_by(
            self.default_order_by
        )
        if order_field:
            data = dictsort(data, order_field, asc)
        return data

    def prepare_results_for_printing(self, results):
        """
        Hook before sending the results for teh printing generator
        :param results: dict containing the data, columns, column_names, verbose_data and other keys
        :return: adjusted results
        """
        return results

    def form_invalid(self, form):
        return JsonResponse(form.errors, status=400)

    # @classmethod
    # def get_default_from_date(cls, **kwargs):
    #     return app_settings.RA_DEFAULT_FROM_DATETIME
    #
    # @classmethod
    # def get_default_to_date(cls, **kwargs):
    #     return app_settings.RA_DEFAULT_TO_DATETIME


class TimeSeriesSelectorReportView(UserPassesTestMixin, SlickReportViewBase):
    @staticmethod
    def form_filter_func(fkeys_dict):
        output = {}
        for k, v in fkeys_dict.items():
            if k not in ["owner_id", "polymorphic_ctype_id", "lastmod_user_id"]:
                output[k] = v
        return output

    @classmethod
    def get_form_class(cls):
        """
        As Report Model might be swapped, form_class cant be accurately generated on model load,
        hence this function.
        :return: form_class
        """
        return cls.form_class or report_form_factory(
            cls.get_report_model(),
            crosstab_model=cls.crosstab_model,
            display_compute_reminder=cls.crosstab_compute_reminder,
            fkeys_filter_func=cls.form_filter_func,
            initial=cls.get_form_initial(),
        )

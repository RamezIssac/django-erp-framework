import logging

from crequest.middleware import CrequestMiddleware
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse, HttpResponseRedirect
from django.template.defaultfilters import capfirst
from django.urls import reverse
from django.views.generic import TemplateView
from slick_reporting.forms import report_form_factory
from slick_reporting.generator import ReportGenerator
from slick_reporting.views import SlickReportViewBase

from erp_framework.base import app_settings
from erp_framework.base.helpers import dictsort
from erp_framework.reporting.forms import OrderByForm
from erp_framework.reporting.printing import HTMLPrintingClass

logger = logging.getLogger("erp_framework.reporting")


class ReportView(SlickReportViewBase):
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

    # to limit records not to exceed certain number, useful for very large reports
    limit_records = False

    perform_regroup_when_print = False  # Handling printing header & sub data

    # size for printing , useful on very large data
    print_buffer = 10000

    # control the caching

    with_type = True

    admin_site_name = "erp_framework"
    template_name = "erp_framework/report.html"

    doc_type_field_name = "doc_type"
    doc_type_plus_list = None
    doc_type_minus_list = None

    def get_context_data(self, **kwargs):
        from erp_framework.sites import erp_admin_site

        context = super().get_context_data(**kwargs)
        extra_context = erp_admin_site.each_context(self.request)
        context.update(extra_context)
        context["is_report"] = True
        try:
            context["current_base_model_name"] = self.base_model.__name__.lower()
        except:
            context["current_base_model_name"] = None

        context["base_model"] = self.base_model
        context["report_slug"] = self.get_report_slug()
        context["CURRENT_REPORT"] = self.__class__
        context["report"] = self

        context["base_template"] = app_settings.report_base_template

        return context

    def get_doc_types_q_filters(self):
        if self.doc_type_plus_list or self.doc_type_minus_list:
            return (
                [Q(**{f"{self.doc_type_field_name}__in": self.doc_type_plus_list})]
                if self.doc_type_plus_list
                else []
            ), (
                [Q(**{f"{self.doc_type_field_name}__in": self.doc_type_minus_list})]
                if self.doc_type_minus_list
                else []
            )

        from erp_framework.doc_types import doc_type_registry

        if self.base_model:
            value = doc_type_registry.get(self.base_model)

            return (
                [Q(**{f"{self.doc_type_field_name}__in": value["plus_list"]})]
                if value["plus_list"]
                else []
            ), (
                [Q(**{f"{self.doc_type_field_name}__in": value["minus_list"]})]
                if value["minus_list"]
                else []
            )

        return [], []

        # return [Q(type__in=doc_types['plus_list'])], [Q(type__in=doc_types['minus_list'])]

    def get_report_generator(self, queryset, for_print):
        q_filters, kw_filters = self.form.get_filters()
        if self.crosstab_field:
            self.crosstab_ids = self.form.get_crosstab_ids()

        crosstab_compute_remainder = (
            self.form.get_crosstab_compute_remainder()
            if self.request.GET or self.request.POST
            else self.crosstab_compute_remainder
        )
        doc_type_plus_list, doc_type_minus_list = [], []

        if self.with_type:
            doc_type_plus_list, doc_type_minus_list = self.get_doc_types_q_filters()

        time_series_pattern = self.time_series_pattern
        if self.time_series_selector:
            time_series_pattern = self.form.get_time_series_pattern()

        return self.report_generator_class(
            self.get_report_model(),
            start_date=self.form.get_start_date(),
            end_date=self.form.get_end_date(),
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
            crosstab_field=self.crosstab_field,
            crosstab_ids=self.crosstab_ids,
            crosstab_columns=self.crosstab_columns,
            crosstab_compute_remainder=crosstab_compute_remainder,
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
        # try:
        #     return cls.base_model._meta.model_name
        # except:
        app_label = cls.__module__.split(".")[0]
        return app_label

    @classmethod
    def get_report_code(cls):
        return f"{cls.get_base_model_name()}.{cls.get_report_slug()}"

    @classmethod
    def get_url(cls):
        return cls.get_absolute_url()

    def get_test_func(self):
        """
        Override this method to use a different test_func method.
        """
        return self.test_func

    @classmethod
    def test_func(cls, request=None, permission="view"):
        return app_settings.report_access_function(request, permission, cls)
        # return True

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            if self.request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
                return JsonResponse({}, status=403)
            else:
                raise PermissionDenied
        return HttpResponseRedirect(reverse("erp_framework:login"))

    @classmethod
    def get_absolute_url(cls):
        request = CrequestMiddleware.get_request()
        try:
            current_app = request.current_app
        except:
            current_app = cls.admin_site_name

        return reverse(
            "admin:report",
            args=(cls.get_base_model_name(), cls.get_report_slug()),
            current_app=current_app,
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
            crosstab_model=cls.crosstab_field,
            display_compute_remainder=cls.crosstab_compute_remainder,
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
        user_test_result = self.get_test_func()(request)
        if not user_test_result:
            return self.handle_no_permission()

        val = super(ReportView, self).dispatch(request, *args, **kwargs)

        return val

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

    def form_invalid(self, form):
        # todo return a page if not ajax
        return JsonResponse(form.errors, status=400)


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
            display_compute_remainder=cls.crosstab_compute_remainder,
            fkeys_filter_func=cls.form_filter_func,
            initial=cls.get_form_initial(),
        )

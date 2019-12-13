from __future__ import unicode_literals

import logging
from functools import update_wrapper
from urllib.parse import urlencode

import simplejson as json
from crequest.middleware import CrequestMiddleware
from django import forms
from django.contrib import admin
from django.contrib.admin.exceptions import DisallowedModelAdminToField
from django.contrib.admin.options import IS_POPUP_VAR, TO_FIELD_VAR, get_content_type_for_model
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.contrib.admin.utils import (quote, unquote, )
from django.contrib.admin.widgets import AdminTextareaWidget, AdminSplitDateTime
from django.contrib.auth import get_permission_codename
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.admin import GenericTabularInline
from django.core.exceptions import PermissionDenied, ImproperlyConfigured
from django.db import models
from django.db.models import DateTimeField, DecimalField, ForeignKey, TextField
from django.db.models.base import ModelBase
from django.forms.widgets import TextInput, NumberInput
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.defaultfilters import capfirst
from django.template.response import TemplateResponse
from django.urls import reverse, path
from django.utils.decorators import method_decorator
from django.utils.encoding import force_text
from django.utils.html import escape
from django.utils.module_loading import import_string
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _, ugettext
from django.views.decorators.csrf import csrf_protect
from tabular_permissions.admin import UserTabularPermissionsMixin, GroupTabularPermissionsMixin

from ra.admin.forms import RaUserChangeForm
from ra.reporting.printing import HTMLPrintingClass
from ra.utils.views import get_print_settings, get_typed_reports_for_templates, get_typed_reports_map, \
    apply_order_to_typed_reports
from .base import RaAdminSiteBase
from ..base import app_settings, loading
from ..base.widgets import AdminSplitDateTimeNoBr, RaBootstrapForeignKeyWidget, \
    RaRelatedFieldWidgetWrapper

csrf_protect_m = method_decorator(csrf_protect)

default_fields = (('title', 'slug'), 'notes')
fields_with_fb = default_fields + ('FB',)
person_fields = default_fields + (('telephone', 'email'), 'address')
person_with_fb = fields_with_fb + (('telephone', 'email'), 'address')

default_exclude = ('owner', 'creation_date', 'lastmod', 'lastmod_user')

default_list_display = ('title', 'slug', 'notes')

logger = logging.getLogger(__name__)

from django.contrib.admin.views.main import ChangeList


def get_reports_map(model_name, user, request, order_list=None):
    """
    Gets ReportViews associated with a specific model ie. namespace
    :param model_name: or namespace defined in ReportView namespace
    :param user: User to check for permissions
    :param order_list: list to order the reports in comparision to

    :return: a dictionary with two values `slugs` and `reports`
        slugs: map to a list of report slugs
        reports: map to a list of ReportView classes
    """

    # todo refine with ra.views.ReportList View
    order_list = list(order_list or [])
    reports = get_typed_reports_for_templates(model_name, user, request)
    reports = apply_order_to_typed_reports(reports, order_list)
    return get_typed_reports_map(typed_reports=reports)


class RaChangeList(ChangeList):
    def __init__(self, request, model, list_display, list_display_links, list_filter, date_hierarchy, search_fields,
                 list_select_related, list_per_page, list_max_show_all, list_editable, model_admin, sortable_by):
        super(RaChangeList, self).__init__(request, model, list_display, list_display_links, list_filter,
                                           date_hierarchy, search_fields, list_select_related, list_per_page,
                                           list_max_show_all, list_editable, model_admin, sortable_by)
        self.request = request  # Add request to the class
        if self.is_popup:
            title = ugettext('Select %s')
        else:
            title = ugettext('%s')
        self.title = title % force_text(self.opts.verbose_name_plural)

        self.no_records_message = model_admin.no_records_message

    def url_for_result(self, result):
        """
        Override parent to handle correct url mapping
        :param result:
        :return:
        """
        if self.model_admin.has_view_permission(self.request):
            pk = getattr(result, self.pk_attname)
            return reverse('%s:%s_%s_view' % (app_settings.RA_ADMIN_SITE_NAME, self.opts.app_label,
                                              self.opts.model_name),
                           args=(quote(pk),),
                           current_app=self.model_admin.admin_site.name)
        elif self.model_admin.has_change_permission(self.request):
            pk = getattr(result, self.pk_attname)
            return reverse('%s:%s_%s_change' % (app_settings.RA_ADMIN_SITE_NAME, self.opts.app_label,
                                                self.opts.model_name),
                           args=(quote(pk),),
                           current_app=self.model_admin.admin_site.name)
        elif self.model_admin.has_add_permission(self.request):
            return reverse('%s:%s_%s_add' % (app_settings.RA_ADMIN_SITE_NAME, self.opts.app_label,
                                             self.opts.model_name),
                           current_app=self.model_admin.admin_site.name)
        return False


class RaAdminSite(RaAdminSiteBase):
    pass


site_class = import_string(app_settings.RA_ADMIN_SITE_CLASS)
ra_admin_site = site_class(name=app_settings.RA_ADMIN_SITE_NAME)

from reversion.admin import VersionAdmin


class RaThemeMixin:
    change_form_template = f'{app_settings.RA_THEME}/change_form.html'
    change_list_template = f'{app_settings.RA_THEME}/change_list.html'
    delete_confirmation_template = f'{app_settings.RA_THEME}/delete_confirmation.html'
    delete_selected_confirmation_template = f'{app_settings.RA_THEME}/delete_selected_confirmation.html'
    add_form_template = f'{app_settings.RA_THEME}/change_form.html'

    recover_form_template = f'{app_settings.RA_THEME}/reversion/recover_form.html'
    revision_form_template = f'{app_settings.RA_THEME}/reversion/revision_form.html'
    object_history_template = f'{app_settings.RA_THEME}/reversion/object_history.html'
    recover_list_template = f'{app_settings.RA_THEME}/reversion/recover_list.html'
    view_template = f'{app_settings.RA_THEME}/view.html'


class RaAdmin(RaThemeMixin, VersionAdmin):
    # ModelAdmin Attributes
    view_on_site = False
    list_per_page = 25
    save_on_top = True
    list_select_related = True
    fields = default_fields
    list_display = ('get_enhanced_obj_title', 'slug', 'notes', 'get_history_link')
    list_display_links = ('slug',)
    date_hierarchy = 'creation_date'

    # Custom templates

    history_latest_first = True
    search_fields = ['title', 'slug']
    formfield_overrides = {
        # DateTimeField: {'widget': AdminSplitDateTime},
        # DecimalField: {'widget': NumberInput},
        # ForeignKey: {'widget': RaBootstrapForeignKeyWidget},
        TextField: {'widget': AdminTextareaWidget(attrs={'rows': 2})}
    }

    # Ra New Attributes
    # ------------------
    description = None  # Description of the model to be displayed in hte changelist filter under the name
    enable_next_serial = True  # Enable the default slug to be a serial number
    enable_view_view = True  # If False there is no "DetailView ie Stats view"
    print_template = None
    no_records_message = _('No Data')

    enable_enter_as_tab = True
    typed_reports_order_list = None
    # new attrs:
    print_settings = {}
    print_title = ''
    print_class = HTMLPrintingClass

    def reversion_register(self, model, **kwargs):
        kwargs['for_concrete_model'] = False
        super(RaAdmin, self).reversion_register(model, **kwargs)

    def get_enhanced_obj_title(self, obj):
        request = CrequestMiddleware.get_request()
        links = []
        pk_attname = self.model._meta.pk.attname
        pk = getattr(obj, pk_attname)
        main_url = False
        if self.has_change_permission(request, obj):
            url = reverse('%s:%s_%s_change' % (app_settings.RA_ADMIN_SITE_NAME, self.model._meta.app_label,
                                               self.model._meta.model_name),
                          args=(quote(pk),),
                          current_app=self.admin_site.name)
            if not main_url: main_url = url
            view_link = '<a href="%s" data-popup="tooltip" title="%s" data-placement="bottom">' \
                        ' <i class="fas fa-edit"></i> </a>' % (
                            url, capfirst(_('change')))
            links.append(view_link)
            links = "<span class='go-to-change-form'>%s</span>" % ''.join(links) + ''
            obj_link_title = "<a href='%s'>%s</a>" % (main_url, obj.title)
            return mark_safe('%s %s' % (obj_link_title, links))
        else:
            return obj.title

    def get_history_link(self, obj):
        info = self.model._meta.app_label, self.model._meta.model_name
        url = reverse('ra_admin:%s_%s_history' % info, args=(obj.pk,))

        return mark_safe("""<a href="%s" class="legitRipple" data-popup="tooltip" title="%s">
                        <i class="fas fa-history text-indigo-800"></i>
                        <span class="legitRipple-ripple"></span></a>""" % (url, _('History')))

    get_history_link.short_description = _('History')

    get_enhanced_obj_title.short_description = _('title')
    get_enhanced_obj_title.admin_order_field = 'title'

    def get_stats_icon(self, obj):
        url = reverse('%s:%s_%s_view' % (app_settings.RA_ADMIN_SITE_NAME, self.model._meta.app_label,
                                         self.model._meta.model_name),
                      args=(quote(obj.pk),),
                      current_app=self.admin_site.name)

        view_link = '<a href="%s" data-popup="tooltip" title="%s %s" data-placement="bottom"> ' \
                    '<i class="fas fa-chart-line"></i> </a>' % (
                        url, capfirst(_('Statistics for')), obj.title)
        return mark_safe(view_link)

    get_stats_icon.short_description = _('Stats')

    def _get_context_report_suffix(self):
        try:
            return self.model().get_pk_name()
        except:
            return self.model.__name__.lower() + '_id'

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['enable_enter_as_tab'] = self.enable_enter_as_tab
        # extra_context['ra_tour_template'] = self.add_form_tour_template
        return super(RaAdmin, self).add_view(request, form_url, extra_context)
    #
    # def get_typed_reports(self, request, **kwargs):
    #     return get_reports_map(self.model.get_class_name().lower(), request.user, request,
    #                            self.typed_reports_order_list)

    # Permissions
    def has_view_permission(self, request, obj=None):
        if not self.enable_view_view:
            return False
        opts = self.opts
        codename = get_permission_codename('view', opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        return super(RaAdmin, self).change_view(request, object_id, form_url, extra_context)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        context['has_view_permission'] = self.has_view_permission(request, obj)
        return super(RaAdmin, self).render_change_form(request, context, add, change, form_url, obj)

    def view_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['has_add_permission'] = self.has_add_permission(request)
        '''
            Code copied from ChangeForm
        '''

        to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
        if to_field and not self.to_field_allowed(request, to_field):
            raise DisallowedModelAdminToField("The field %s cannot be referenced." % to_field)

        model = self.model
        opts = model._meta
        add = object_id is None

        if add:
            if not self.has_add_permission(request):
                raise PermissionDenied
            obj = None

        else:
            obj = self.get_object(request, unquote(object_id), to_field)

            if not self.has_view_permission(request, obj):
                raise PermissionDenied

            if obj is None:
                raise Http404(_('%(name)s object with primary key %(key)r does not exist.') % {
                    'name': force_text(opts.verbose_name), 'key': escape(object_id)})

                # if request.method == 'POST' and "_saveasnew" in request.POST:
                #     return self.add_view(request, form_url=reverse('admin:%s_%s_add' % (
                #         opts.app_label, opts.model_name), current_app=self.admin_site.name))
        context = dict(self.admin_site.each_context(request),
                       title=obj,
                       app_label=opts.app_label,
                       object_id=object_id,
                       original=obj,
                       is_popup=(IS_POPUP_VAR in request.POST or
                                 IS_POPUP_VAR in request.GET),
                       to_field=to_field,
                       # media=media,
                       preserved_filters=self.get_preserved_filters(request),
                       )

        context.update(extra_context or {})

        opts = self.model._meta
        app_label = opts.app_label
        preserved_filters = self.get_preserved_filters(request)
        form_url = add_preserved_filters({'preserved_filters': preserved_filters, 'opts': opts}, form_url)
        view_on_site_url = self.get_view_on_site_url(obj)
        context.update({
            'add': add,
            'change': not add,
            'has_add_permission': self.has_add_permission(request),
            'has_change_permission': self.has_change_permission(request, obj),
            'has_delete_permission': self.has_delete_permission(request, obj),
            'has_file_field': True,
            'has_absolute_url': view_on_site_url is not None,
            'absolute_url': view_on_site_url,
            'form_url': form_url,
            'opts': opts,
            'content_type_id': get_content_type_for_model(self.model).pk,
            'save_as': self.save_as,
            'save_on_top': self.save_on_top,
            'to_field_var': TO_FIELD_VAR,
            'is_popup_var': IS_POPUP_VAR,
            'app_label': app_label,
        })

        request.current_app = self.admin_site.name
        return TemplateResponse(request, self.view_template or [
            "admin/%s/%s/view.html" % (opts.app_label, opts.model_name),
            "admin/%s/view.html" % opts.app_label,
            f"{app_settings.RA_THEME}/view.html",
        ], context)

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['description'] = self.description
        return super(RaAdmin, self).changelist_view(request, extra_context)

    def get_changelist(self, request, **kwargs):
        return RaChangeList

    def save_model(self, request, obj, form, change):
        obj.lastmod_user = request.user
        obj.lastmod_date = now()
        if not change:
            obj.owner = request.user
            obj.creation_date = now()
        super(RaAdmin, self).save_model(request, obj, form, change)

    def get_urls(self):
        # Override ModelAdmin
        from django.conf.urls import url

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name
        admin_site = self.admin_site
        reversion_urls = [
            url("^recover/$", admin_site.admin_view(self.recoverlist_view),
                name='%s_%s_recoverlist' % info),
            url("^recover/([^/]+)/$", admin_site.admin_view(self.recover_view),
                name='%s_%s_recover' % info),
            url("^([^/]+)/history/([^/]+)/$", admin_site.admin_view(self.revision_view),
                name='%s_%s_revision' % info),
        ]

        urlpatterns = [
            url(r'^$', wrap(self.changelist_view), name='%s_%s_changelist' % info),
            url(r'^add/$', wrap(self.add_view), name='%s_%s_add' % info),
            url(r'^(.+)/history/$', wrap(self.history_view), name='%s_%s_history' % info),
            url(r'^(.+)/delete/$', wrap(self.delete_view), name='%s_%s_delete' % info),
            url(r'^(.+)/change/$', wrap(self.change_view), name='%s_%s_change' % info),
        ]
        # url(r'^(.+)/$', wrap(self.view_view), name='%s_%s_view' % info),
        if self.enable_view_view:
            urlpatterns += [
                url(r'^(.+)/$', wrap(self.view_view), name='%s_%s_view' % info),
            ]

        # End Override
        # ------------------------------------------------------------------------------

        my_urls = [
            path('autocomplete/', wrap(self.autocomplete_view), name='%s_%s_autocomplete' % info),
            url(r'^check/(?P<slug>[\w-]+)/$', self.admin_site.admin_view(self.check_view)),
            url(r'^slug/(?P<slug>[\w-]+)/$', self.admin_site.admin_view(self.get_by_slug)),
        ]
        return my_urls + reversion_urls + urlpatterns

    def get_by_slug(self, request, **kwargs):
        result, query = self.model.simple_query(**kwargs)
        if result:
            query = query[0]
            admin_url = reverse('%s:%s_%s_change' % (
                app_settings.RA_ADMIN_SITE_NAME, self.model._meta.app_label, self.model._meta.model_name),
                                args=(query.id,))
            return HttpResponseRedirect(admin_url)
        else:
            raise Http404

    def check_view(self, request, **kwargs):
        results = self.model.simple_query(**kwargs)
        if results:
            result, query = results
        else:
            result, query = None, None
        if result:
            query = query[0]
            admin_url = reverse('admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name),
                                args=(query.id,))
            is_new = False
        else:
            admin_url = reverse('%s:%s_%s_add' % (
                app_settings.RA_ADMIN_SITE_NAME, self.model._meta.app_label, self.model._meta.model_name))
            admin_url += '?%s' % urlencode(kwargs)
            is_new = True

        context = {
            'result': True,
            'is_new': is_new,
            'admin_url': admin_url
        }
        return HttpResponse(json.dumps(context), content_type="application/json")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.ForeignKey):
            if db_field.__class__ in self.formfield_overrides:
                kwargs = dict(self.formfield_overrides[db_field.__class__], **kwargs)

            formfield = self.formfield_for_foreignkey(db_field, request, **kwargs)
            if formfield and db_field.name not in self.raw_id_fields:
                related_modeladmin = self.admin_site._registry.get(db_field.remote_field.model)
                wrapper_kwargs = {}
                if related_modeladmin:
                    wrapper_kwargs.update(
                        can_add_related=related_modeladmin.has_add_permission(request),
                        can_change_related=related_modeladmin.has_change_permission(request),
                        can_delete_related=related_modeladmin.has_delete_permission(request),
                    )
                    formfield.widget = RaRelatedFieldWidgetWrapper(
                        formfield.widget, db_field.remote_field, self.admin_site, **wrapper_kwargs
                    )
            return app_settings.RA_FORMFIELD_FOR_DBFIELD_FUNC(self, db_field, formfield, request, **kwargs)

        # if db_field.name == 'doc_date' and db_field.__class__ == DateTimeField:
        #     field = forms.SplitDateTimeField(widget=AdminSplitDateTimeNoBr, label=_('Date'))
        # else:
        field = super(RaAdmin, self).formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'slug' and self.enable_next_serial:
            field.initial = self.get_next_serial()
        elif db_field.name == 'doc_date':

            field.initial = now()
        return app_settings.RA_FORMFIELD_FOR_DBFIELD_FUNC(self, db_field, field, request, **kwargs)

    def get_next_serial(self):
        from ra.base.helpers import get_next_serial

        return get_next_serial(self.model)

    def whole_changeform_validation(self, request, form, formsets, change, **kwargs):
        '''
        A Hook for validating the whole changeform
        :param form: the ModelAdmin Form
        :param formsets: inline formsets
        :param kwargs: extra kwargs
        :return: True for valid [default] False for Invalid
        '''
        return True

    def pre_save(self, form, formsets, change):
        """
        Hook for doing any final computation setting before saving
        :param form:
        :param formsets:
        :param change:
        :return:
        """
        pass

    def post_save(self, request, new_object, form, formsets, change):
        """
        Hook for doing any final logic after saving
        :param form:
        :param formsets:
        :param change:
        :return:
        """
        pass

    # -------
    # Printing
    # -------
    def get_printing_class(self, request, object_id=None, form_url='', extra_context=None):
        return self.print_class

    def get_print_sub_title(self, print_theme, request=None, object_id=None, obj=None, **kwargs):
        return getattr(obj, 'doc_date', '')

    def get_print_title(self, print_theme, request=None, object_id=None, obj=None, **kwargs):
        if not self.print_title:
            if self.model:
                return force_text(u'%s - %s' % (self.model._meta.verbose_name, obj.slug))
            return u''
        return force_text(self.print_title)

    def get_print_settings(self, print_theme):
        # duplicated in MainReportFactory
        default_print_settings = get_print_settings()
        default_print_settings['pre_header_template'] = 'ra/tex/formset_pre_table.html'

        print_setting = self.print_settings or {}
        print_setting = print_setting.get(print_theme, {})
        default_print_settings.update(print_setting)
        return default_print_settings.copy()

    def get_print_data(self, request, form, formsets, object_id=None, form_url='', extra_context=None):
        """
        Return Columns , column_names and data tuple
        :param request:
        :param object_id:
        :param form_url:
        :param extra_context:
        :return: (columns, column_names, data, doc_date)
        """

        formset = None
        if formsets:
            formset = formsets[0]

        columns, column_names = self._get_columns_data(formset)
        data = self._get_data_from_formset(formset, columns, object_id, extra_context)
        doc_date = self.get_obj_print_date(request, formset)
        return columns, column_names, data, doc_date

    def _get_columns_data(self, formset, *args, **kwargs):
        if not formset:
            return [], []
        column_names = []
        columns = []
        for field_name in formset[0].fields.keys():
            if field_name != 'DELETE':
                if not formset[0].fields[field_name].widget.is_hidden:
                    columns.append(field_name)
                    column_names.append(force_text(formset[0].fields[field_name].label))
        return columns, column_names

    def _get_data_from_formset(self, formset, columns, object_id, extra_context):
        BaseInfo = loading.get_baseinfo_model()
        BaseMovementInfo = loading.get_basemovementinfo_model()
        data = []
        if formset:
            for form in formset.queryset:
                data_line = {}
                for field_name in columns:
                    try:
                        field = form.__getattribute__(field_name)
                    except:
                        field = ''

                    mro = type(field).__mro__
                    # info = ''

                    if BaseInfo in mro:
                        info = field.title
                    elif BaseMovementInfo in mro:
                        info = field.slug
                    else:
                        info = field

                    data_line[field_name] = info
                data.append(data_line)
        return data

    def get_obj_print_date(self, request, formset, object_id=None, form_url='', extra_context=None):
        if formset:
            return formset.instance.doc_date
        return now()

    def get_print_template(self, request, print_theme=None, **kwargs):
        """
        Return the print template
        :param request:
        :param print_theme: if any
        :param kwargs:
        :return:
        """
        return self.print_template

    def print_document(self, request, object_id=None, form_url='', extra_context=None):

        to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
        if to_field and not self.to_field_allowed(request, to_field):
            raise DisallowedModelAdminToField("The field %s cannot be referenced." % to_field)

        download = request.GET.get('download', False)
        add = object_id is None
        model = self.model
        opts = model._meta

        if add:
            if not self.has_add_permission(request):
                raise PermissionDenied
            obj = None

        else:
            obj = self.get_object(request, unquote(object_id), to_field)

            if not self.has_change_permission(request, obj):
                raise PermissionDenied

            if obj is None:
                raise Http404(_('%(name)s object with primary key %(key)r does not exist.') % {
                    'name': force_text(opts.verbose_name), 'key': escape(object_id)})

        ModelForm = self.get_form(request, obj)
        if add:
            initial = self.get_changeform_initial_data(request)
            form = ModelForm(initial=initial)
            formsets, inline_instances = self._create_formsets(request, self.model(), change=False)
        else:
            form = ModelForm(instance=obj)
            formsets, inline_instances = self._create_formsets(request, obj, change=True)
        extra_context['obj'] = obj
        print_theme = request.GET.get('print_theme', 'default')
        extra_context['theme'] = print_theme
        columns, column_names, data, doc_date = self.get_print_data(request, form, formsets, object_id, form_url,
                                                                    extra_context)
        print_settings = self.get_print_settings(print_theme)
        response = {
            'is_group': True,
            'columns': columns,
            'column_names': column_names,
            'data': data,
            'report_title': self.get_print_title(print_theme, request, object_id, obj),
            'report_sub_title': self.get_print_sub_title(print_theme, request, object_id, obj),
            'form_settings': {
                'doc_date': doc_date,
            },
            'print_settings': print_settings,
        }

        if formsets:
            extra_context['formset'] = formsets[0]
            extra_context['formsets'] = formsets
        extra_context['form'] = form
        print_klass = self.get_printing_class(request, object_id, form_url, extra_context)
        print_class = print_klass(request, form_settings=response['form_settings'], response=response,
                                  print_settings=print_settings)

        return print_class.get_response(template_name=self.get_print_template(request, print_theme))

    def get_actions(self, request):
        actions = super(RaAdmin, self).get_actions(request)
        if not (app_settings.RA_ENABLE_ADMIN_DELETE_ALL and request.user.is_superuser):
            if 'delete_selected' in actions:
                del actions['delete_selected']
        return actions

    def get_list_display(self, request):
        list_display = super(RaAdmin, self).get_list_display(request)

        if self.has_view_permission(request):
            list_display = ('get_stats_icon',) + list_display

        return list_display


class RaMovementAdmin(RaAdmin):
    enable_view_view = False
    list_per_page = 50
    view_on_site = False
    list_display = ('slug', 'doc_date', 'get_history_link')
    list_display_links = ('slug', 'doc_date')
    fields = (('slug', 'doc_date'),)
    exclude = ('doc_type',)
    formfield_overrides = {
        # DateTimeField: {'widget': AdminSplitDateTimeNoBr},
        # DecimalField: {'widget': NumberInput},
        # ForeignKey: {'widget': RaBootstrapForeignKeyWidget},
    }
    date_hierarchy = 'doc_date'
    doc_type = None
    copy_to_formset = None

    copy_form_notes_to_formset = False
    search_fields = ['doc_date', 'slug']

    def __init__(self, *args, **kwargs):
        super(RaMovementAdmin, self).__init__(*args, **kwargs)
        self.copy_to_formset = self.copy_to_formset or []

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        form_field = super(RaMovementAdmin, self).formfield_for_dbfield(db_field, request, **kwargs)
        form_field = app_settings.RA_FORMFIELD_FOR_DBFIELD_FUNC(self, db_field, form_field, request, **kwargs)
        return form_field

    def save_formset(self, request, form, formset, change):
        for formset_form in formset:
            formset_form.instance.doc_date = form.instance.doc_date
            formset_form.instance.doc_type = form.instance.doc_type
            formset_form.instance.slug = form.instance.slug
            formset_form.instance.lastmod_user = request.user
            if self.copy_form_notes_to_formset:
                formset_form.instance.notes = form.instance.notes
            for copy_item in self.copy_to_formset:
                formset_form.instance.__setattr__(copy_item, form.instance.__getattribute__(copy_item))
                # print(copy_item, form.instance.__getattribute__(copy_item))
            if formset_form.instance.pk is not None:
                formset_form.instance.save()
        formset.save()

    def get_list_display(self, request):
        list_display = super(RaMovementAdmin, self).get_list_display(request)
        return list_display


class RaMovementInlineAdmin(admin.TabularInline):
    template = f'{app_settings.RA_THEME}/edit_inline/tabular.html'
    extra = 2
    exclude = ('slug', 'doc_date', 'doc_type', 'lastmod', 'lastmod_user', 'owner', 'creation_date')
    formfield_overrides = {
        models.TextField: {'widget': TextInput},
        DecimalField: {'widget': NumberInput},
        # ForeignKey: {'widget': RaBootstrapForeignKeyWidget},

    }
    view_on_site = False

    '''
    To simplify complex forms with inline , making inline permission reflect base form permission
    permission_override_model can be True, False , str Or ModelBase
    '''
    permission_override_model = True

    def get_ra_permission_codename(self, action, model_name):
        """
        Returns the codename of the permission for the specified action.
        """
        return '%s_%s' % (action, model_name)

    def get_permission_override_model(self, request, **kwargs):
        """
        Return a string reprsentation of the model to look into its permissions,
        :param request:
        :param kwargs:
        :return:
        """
        if self.permission_override_model is True:
            return self.parent_model._meta.model_name

        elif type(self.permission_override_model) is str:
            return self.permission_override_model

        elif type(self.permission_override_model) is ModelBase:
            return self.permission_override_model._meta.model_name

        else:
            raise ImproperlyConfigured(
                'self.permission_override_model can be True, False , str or ModelBase .Got %s instead ' % type(
                    self.permission_override_model))

    def has_add_permission(self, request, obj=None):
        if self.opts.auto_created:
            # We're checking the rights to an auto-created intermediate model,
            # which doesn't have its own individual permissions. The user needs
            # to have the change permission for the related model in order to
            # be able to do anything with the intermediate model.
            return self.has_change_permission(request)
        opts = self.opts
        if self.permission_override_model:
            model_name = self.get_permission_override_model(request)
            codename = self.get_ra_permission_codename('add', model_name)
        else:
            codename = get_permission_codename('add', opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))

    def has_change_permission(self, request, obj=None):
        opts = self.opts
        if opts.auto_created:
            # The model was auto-created as intermediary for a
            # ManyToMany-relationship, find the target model
            for field in opts.fields:
                if field.remote_field and field.remote_field.model != self.parent_model:
                    opts = field.remote_field.model._meta
                    break
        if self.permission_override_model:
            model_name = self.get_permission_override_model(request)
            codename = self.get_ra_permission_codename('change', model_name)
        else:
            codename = get_permission_codename('change', opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))

    def has_delete_permission(self, request, obj=None):
        if self.opts.auto_created:
            # We're checking the rights to an auto-created intermediate model,
            # which doesn't have its own individual permissions. The user needs
            # to have the change permission for the related model in order to
            # be able to do anything with the intermediate model.
            return self.has_change_permission(request, obj)
        opts = self.opts
        if self.permission_override_model:
            model_name = self.get_permission_override_model(request)
            codename = self.get_ra_permission_codename('delete', model_name)
        else:
            codename = get_permission_codename('delete', opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.ForeignKey):
            if db_field.__class__ in self.formfield_overrides:
                kwargs = dict(self.formfield_overrides[db_field.__class__], **kwargs)

            formfield = self.formfield_for_foreignkey(db_field, request, **kwargs)
            if formfield and db_field.name not in self.raw_id_fields:
                related_modeladmin = self.admin_site._registry.get(db_field.remote_field.model)
                wrapper_kwargs = {}
                if related_modeladmin:
                    wrapper_kwargs.update(
                        can_add_related=related_modeladmin.has_add_permission(request),
                        can_change_related=related_modeladmin.has_change_permission(request),
                        can_delete_related=related_modeladmin.has_delete_permission(request),
                    )
                    formfield.widget = RaRelatedFieldWidgetWrapper(
                        formfield.widget, db_field.remote_field, self.admin_site, **wrapper_kwargs
                    )
        form_field = super(RaMovementInlineAdmin, self).formfield_for_dbfield(db_field, request, **kwargs)
        form_field = app_settings.RA_FORMFIELD_FOR_DBFIELD_FUNC(self, db_field, form_field, request, **kwargs)
        return form_field


class RaGenericTabularInline(GenericTabularInline):
    """
    Implementation of teh needed methods for Generic Tabular inline with RA
    """
    extra = 1
    exclude = ('slug', 'doc_date', 'doc_type', 'lastmod', 'lastmod_user', 'owner', 'creation_date')
    formfield_overrides = {
        TextField: {'widget': TextInput},
        DecimalField: {'widget': NumberInput},
        ForeignKey: {'widget': RaBootstrapForeignKeyWidget},

    }
    view_on_site = False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.ForeignKey):
            if db_field.__class__ in self.formfield_overrides:
                kwargs = dict(self.formfield_overrides[db_field.__class__], **kwargs)

            formfield = self.formfield_for_foreignkey(db_field, request, **kwargs)
            if formfield and db_field.name not in self.raw_id_fields:
                related_modeladmin = self.admin_site._registry.get(db_field.remote_field.model)
                wrapper_kwargs = {}
                if related_modeladmin:
                    wrapper_kwargs.update(
                        can_add_related=related_modeladmin.has_add_permission(request),
                        can_change_related=related_modeladmin.has_change_permission(request),
                        can_delete_related=related_modeladmin.has_delete_permission(request),
                    )
                    formfield.widget = RaRelatedFieldWidgetWrapper(
                        formfield.widget, db_field.remote_field, self.admin_site, **wrapper_kwargs
                    )
        form_field = super(RaGenericTabularInline, self).formfield_for_dbfield(db_field, request, **kwargs)
        form_field = app_settings.RA_FORMFIELD_FOR_DBFIELD_FUNC(self, db_field, form_field, request, **kwargs)
        return form_field


class PrepopulatedAdmin(object):
    prepopulation_querysets = None
    prepopulation_fields = None
    prepopulation_fields_from = None
    prepopulated_inlines = []  # a subset of inlines that will be prepopulated
    prepopulation_extra_data = None  # to do A list of fields

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['prepopulation_fields'] = self.prepopulation_fields
        return super(PrepopulatedAdmin, self).add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['prepopulation_fields'] = self.prepopulation_fields
        return super(PrepopulatedAdmin, self).change_view(request, object_id, form_url, extra_context)

    def get_prepopulattion_queryset(self, inline):
        return self.prepopulation_querysets.get(inline.__class__, None)

    def get_prepopulation_queryset(self, inline, inline_queryset, request, obj, change):
        '''
        return a queryset Or None
        '''
        try:
            return self.prepopulation_querysets.get(inline.__class__, None)
        except AttributeError:
            raise ImproperlyConfigured('Please check %s.prepopulation_querysets to be a dict type' % self.__class__)

    def filter_inline_queryset(self, inline_queryset, request, obj, change):
        f = self._get_inline_queryset_filter(inline_queryset)
        if f:
            inline_queryset = inline_queryset.filter(**{f: obj})
        return inline_queryset

    def _get_inline_queryset_filter(self, inline_queryset):
        fields = inline_queryset.model._meta.get_fields()
        for f in fields:
            if type(f) is ForeignKey:
                if f.related_model in self.model.__mro__:
                    return f.name
        return ''

    def get_prepopulation_extra_data(self, inline, data):
        '''
        Hook to add Extra data (other then prepoputation field) to the prepopulated form
        '''
        return {}

    def get_formset_initial(self, inline, inline_queryset, request, obj, change):
        self.prepopulation_fields_from = self.prepopulation_fields_from or {}

        prepopulateion_queryset = self.get_prepopulation_queryset(inline, inline_queryset, request, obj, change)
        prepopulation_field = self.prepopulation_fields.get(inline.__class__, None)
        prepopulation_field_from = self.prepopulation_fields_from.get(inline.__class__, 'id')
        prepopulation_field_from = prepopulation_field_from if prepopulation_field_from == 'id' \
            else '%s_id' % prepopulation_field_from

        if prepopulateion_queryset is None:
            return []
        else:
            assert prepopulation_field is not None
            initial_data = prepopulateion_queryset.values(prepopulation_field_from)

            id_list = [x[prepopulation_field_from] for x in initial_data]
            initial_data = [x for x in initial_data]
            return_data = []
            if change:
                filtered_queryset = self.filter_inline_queryset(inline_queryset, request, obj, change)
                for item in filtered_queryset:
                    try:
                        x = id_list.index(item.__getattribute__('%s_id' % prepopulation_field))
                        id_list.pop(x)
                        initial_data.pop(x)
                    except ValueError:
                        pass
                for i, data in enumerate(initial_data):
                    return_data.append({prepopulation_field: initial_data[i][prepopulation_field_from]})
                request._initial_data = return_data
                return return_data

            elif not change:
                ret_val = []
                for item in initial_data:
                    ret_val.append({prepopulation_field: item[prepopulation_field_from]})
                return ret_val

        return []

    def _create_formsets(self, request, obj, change):
        "Helper function to generate formsets for add/change_view."
        formsets = []
        inline_instances = []
        prefixes = {}
        get_formsets_args = [request]
        if change:
            get_formsets_args.append(obj)
        for FormSet, inline in self.get_formsets_with_inlines(*get_formsets_args):
            prefix = FormSet.get_default_prefix()
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
            if prefixes[prefix] != 1 or not prefix:
                prefix = "%s-%s" % (prefix, prefixes[prefix])
            inline_queryset = inline.get_queryset(request)
            formset_params = {
                'instance': obj,
                'prefix': prefix,
                'queryset': inline_queryset,
            }
            if request.method == 'POST':
                formset_params.update({
                    'data': request.POST,
                    'files': request.FILES,
                    'save_as_new': '_saveasnew' in request.POST
                })
            else:
                initial_data = self.get_formset_initial(inline, inline_queryset, request, obj, change)
                # Not here is a necessity, in case you find unuseful revise again
                if inline.__class__ in self.prepopulated_inlines or not self.prepopulated_inlines:
                    FormSet.extra = len(initial_data)
                if initial_data:
                    formset_params.update({
                        'initial': initial_data,
                    })
            formsets.append(FormSet(**formset_params))
            inline_instances.append(inline)
        return formsets, inline_instances


class RaPrePopulatedAdmin(PrepopulatedAdmin, RaAdmin):
    change_form_template = 'ra/admin/change_form_prepopulated.html'
    add_form_template = 'ra/admin/change_form_prepopulated.html'


class RaMovementPrepopulatedAdmin(RaPrePopulatedAdmin):
    enable_view_view = False
    list_per_page = 50
    copy_to_formset = []
    copy_form_notes_to_formset = False

    def save_formset(self, request, form, formset, change):
        for formset_form in formset:
            formset_form.instance.doc_date = form.instance.doc_date
            formset_form.instance.doc_type = form.instance.doc_type
            formset_form.instance.slug = form.instance.slug
            formset_form.instance.lastmod_user = request.user
            if self.copy_form_notes_to_formset:
                formset_form.instance.notes = form.instance.notes
            for copy_item in self.copy_to_formset:
                formset_form.instance.__setattr__(copy_item, form.instance.__getattribute__(copy_item))

        formset.save()


class RaUserAdmin(RaThemeMixin, UserTabularPermissionsMixin, UserAdmin):
    enable_view_view = False
    date_hierarchy = None
    fields = None
    list_display_links = ['username']
    change_user_password_template = f'{app_settings.RA_THEME}/auth/user/change_password.html'
    list_display = ('username', 'is_superuser', 'last_login', 'is_active')

    save_on_top = True

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': (('first_name', 'last_name', 'email'),)}),
        (_('Permissions'), {'fields': (('is_active', 'is_superuser'),
                                       'groups', 'user_permissions')}),
        # (_('Important dates'), {'fields': (('last_login', 'date_joined'),)}),
    )
    list_filter = ('is_superuser', 'is_active', 'groups')
    form = RaUserChangeForm

    def get_actions(self, request):
        actions = super(RaUserAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.is_staff = True
        super(RaUserAdmin, self).save_model(request, obj, form, change)

    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        return super(RaUserAdmin, self).get_inline_instances(request, obj)

    def changelist_view(self, request, extra_context=None):
        extra_context = {
            'has_detached_sidebar': True
        }
        return super(RaUserAdmin, self).changelist_view(request, extra_context)


class RaGroupAdmin(RaThemeMixin, GroupTabularPermissionsMixin, GroupAdmin):
    enable_view_view = False
    date_hierarchy = None
    fields = None
    list_display_links = ['name']
    list_display = ['name']

    save_on_top = True


ra_admin_site.register(Group, RaGroupAdmin)
ra_admin_site.register(User, RaUserAdmin)

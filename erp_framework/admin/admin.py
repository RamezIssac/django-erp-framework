from __future__ import unicode_literals

import logging

from crequest.middleware import CrequestMiddleware
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.admin.exceptions import DisallowedModelAdminToField
from django.contrib.admin.options import (
    IS_POPUP_VAR,
    TO_FIELD_VAR,
    get_content_type_for_model,
)
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.contrib.admin.utils import quote, unquote, flatten_fieldsets
from django.contrib.admin.widgets import AdminTextareaWidget, RelatedFieldWidgetWrapper
from django.contrib.auth import get_permission_codename
from django.contrib.contenttypes.admin import GenericTabularInline
from django.core.exceptions import PermissionDenied, ImproperlyConfigured
from django.db import models
from django.db.models import DecimalField, ForeignKey, TextField
from django.db.models.base import ModelBase
from django.dispatch import Signal
from django.forms import all_valid
from django.forms.widgets import TextInput, NumberInput
from django.http import HttpResponseRedirect, Http404
from django.template.defaultfilters import capfirst
from django.template.response import TemplateResponse
from django.urls import reverse, path
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from reversion.admin import VersionAdmin

from erp_framework.base.helpers import flatten_list
from erp_framework.reporting.printing import HTMLPrintingClass
from .base import ERPFrameworkAdminSiteBase
from ..base import app_settings

csrf_protect_m = method_decorator(csrf_protect)

default_fields = (("name", "slug"), "notes")

default_exclude = ("owner", "creation_date", "lastmod", "lastmod_user")

default_list_display = ("name", "slug", "notes")

logger = logging.getLogger(__name__)

# todo bring back
# changeform_saved = Signal(providing_args=["instance", "created", 'using'])
changeform_saved = Signal()


class ERPFrameworkAdminSite(ERPFrameworkAdminSiteBase):
    pass


class RaThemeMixin:
    change_form_template = f"{app_settings.ERP_FRAMEWORK_THEME}/change_form.html"
    change_list_template = f"{app_settings.ERP_FRAMEWORK_THEME}/change_list.html"
    delete_confirmation_template = (
        f"{app_settings.ERP_FRAMEWORK_THEME}/delete_confirmation.html"
    )
    delete_selected_confirmation_template = (
        f"{app_settings.ERP_FRAMEWORK_THEME}/delete_selected_confirmation.html"
    )
    add_form_template = f"{app_settings.ERP_FRAMEWORK_THEME}/change_form.html"

    recover_form_template = f"erp_framework/reversion/recover_form.html"
    revision_form_template = f"erp_framework/reversion/revision_form.html"
    object_history_template = f"erp_framework/reversion/object_history.html"
    recover_list_template = f"erp_framework/reversion/recover_list.html"

    view_template = None  # Defaults to f'{app_settings.ERP_FRAMEWORK_THEME}/view.html'


class AdminViewMixin(admin.ModelAdmin):
    enable_view_view = True
    view_fields = ()
    view_template = "erp_framework/view.html"

    def get_stats_icon(self, obj):
        url = reverse(
            "%s:%s_%s_view"
            % ("admin", self.model._meta.app_label, self.model._meta.model_name),
            args=(quote(obj.pk),),
            current_app=self.admin_site.name,
        )

        # todo change the str obj
        view_link = (
                '<a href="%s" data-popup="tooltip" name="%s %s" data-placement="bottom"> '
                '<i class="fas fa-chart-line"></i> </a>'
                % (url, capfirst(_("Statistics for")), str(obj))
        )
        return mark_safe(view_link)

    get_stats_icon.short_description = _("Stats")

    def get_view_fields(self, request, obj=None):
        return (
                self.view_fields
                or [x for x in flatten_list(self.fields)]
                or self.get_fields(request, obj)
        )

    def get_view_title(self, request, obj=None):
        return _("View %s") % str(obj)
        # return self.get_title(request, obj)

    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name

        my_urls = [
            path(
                "<path:object_id>/view/",
                self.admin_site.admin_view(self.view_view),
                name="%s_%s_view" % info,
            )
        ]
        return my_urls + urls

    def has_view_permission(self, request, obj=None):
        if not self.enable_view_view:
            return False
        opts = self.opts
        codename = get_permission_codename("view", opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))

    def view_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["has_add_permission"] = self.has_add_permission(request)

        to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
        if to_field and not self.to_field_allowed(request, to_field):
            raise DisallowedModelAdminToField(
                "The field %s cannot be referenced." % to_field
            )

        model = self.model
        opts = model._meta

        obj = self.get_object(request, unquote(object_id), to_field)

        if not self.has_view_permission(request, obj):
            raise PermissionDenied

        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, opts, object_id)

        data = []
        view_fields = self.get_view_fields(request, obj)
        for field_name in view_fields:
            # field = self.get_field(request, obj, field_name)
            field = model._meta.get_field(field_name)
            if field:
                data.append((field.verbose_name, field.value_from_object(obj)))

        context = dict(
            self.admin_site.each_context(request),
            name=obj,
            app_label=opts.app_label,
            object_id=object_id,
            original=obj,
            is_popup=(IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET),
            to_field=to_field,
            # media=media,
            title=self.get_view_title(request, obj),
            data=data,
            preserved_filters=self.get_preserved_filters(request),
        )

        context.update(extra_context or {})

        opts = self.model._meta
        app_label = opts.app_label
        preserved_filters = self.get_preserved_filters(request)
        form_url = add_preserved_filters(
            {"preserved_filters": preserved_filters, "opts": opts}, form_url
        )
        view_on_site_url = self.get_view_on_site_url(obj)
        context.update(
            {
                # 'add': add,
                # 'change': not add,
                "has_add_permission": self.has_add_permission(request),
                "has_change_permission": self.has_change_permission(request, obj),
                "has_view_permission": self.has_view_permission(request, obj),
                "has_delete_permission": self.has_delete_permission(request, obj),
                "has_file_field": True,
                "has_absolute_url": view_on_site_url is not None,
                "absolute_url": view_on_site_url,
                "form_url": form_url,
                "opts": opts,
                "content_type_id": get_content_type_for_model(self.model).pk,
                "save_as": self.save_as,
                "save_on_top": self.save_on_top,
                "to_field_var": TO_FIELD_VAR,
                "is_popup_var": IS_POPUP_VAR,
                "app_label": app_label,
            }
        )

        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            self.view_template
            or [
                "erp_framework/%s/%s/view.html" % (opts.app_label, opts.model_name),
                "erp_framework/%s/view.html" % opts.app_label,
                "erp_framework/view.html",
                f"{app_settings.ERP_FRAMEWORK_THEME}/view.html",
            ],
            context,
        )


class EntityAdmin(RaThemeMixin, AdminViewMixin, VersionAdmin):
    # ModelAdmin Attributes
    view_on_site = False
    list_per_page = 25
    save_on_top = True
    list_select_related = True
    fields = default_fields
    list_display = ("get_enhanced_obj_title", "slug", "notes", "get_history_link")
    list_display_links = ("slug",)
    date_hierarchy = "creation_date"

    # Custom templates

    history_latest_first = True
    search_fields = ["name", "slug"]
    formfield_overrides = {
        # DateTimeField: {'widget': AdminSplitDateTime},
        # DecimalField: {'widget': NumberInput},
        # ForeignKey: {'widget': RaBootstrapForeignKeyWidget},
        TextField: {"widget": AdminTextareaWidget(attrs={"rows": 2})}
    }

    # Ra New Attributes
    # ------------------
    description = None  # Description of the model to be displayed in hte changelist filter under the name
    enable_next_serial = True  # Enable the default slug to be a serial number
    enable_view_view = True  # If False there is no "DetailView ie Stats view"
    print_template = None
    no_records_message = _("No Data")

    typed_reports_order_list = None
    # new attrs:
    print_settings = {}
    print_title = ""
    print_class = HTMLPrintingClass

    def reversion_register(self, model, **kwargs):
        kwargs["for_concrete_model"] = False
        super(EntityAdmin, self).reversion_register(model, **kwargs)

    def get_enhanced_obj_title(self, obj):
        request = CrequestMiddleware.get_request()
        links = []
        pk_attname = self.model._meta.pk.attname
        pk = getattr(obj, pk_attname)
        main_url = False
        if self.has_change_permission(request, obj):
            url = reverse(
                "%s:%s_%s_change"
                % (
                    app_settings.ERP_FRAMEWORK_SITE_NAME,
                    self.model._meta.app_label,
                    self.model._meta.model_name,
                ),
                args=(quote(pk),),
                current_app=self.admin_site.name,
            )
            if not main_url:
                main_url = url
            view_link = (
                    '<a href="%s" data-popup="tooltip" name="%s" data-placement="bottom">'
                    ' <i class="fas fa-edit"></i> </a>' % (url, capfirst(_("change")))
            )
            links.append(view_link)
            links = "<span class='go-to-change-form'>%s</span>" % "".join(links) + ""
            obj_link_title = "<a href='%s'>%s</a>" % (main_url, obj.name)
            return mark_safe("%s %s" % (obj_link_title, links))

        return obj.name

    def get_history_link(self, obj):
        info = self.model._meta.app_label, self.model._meta.model_name
        url = reverse("erp_framework:%s_%s_history" % info, args=(obj.pk,))

        return mark_safe(
            """<a href="%s" class="legitRipple" data-popup="tooltip" name="%s">
                        <i class="fas fa-history text-indigo-800"></i>
                        <span class="legitRipple-ripple"></span></a>"""
            % (url, _("History"))
        )

    get_history_link.short_description = _("History")

    get_enhanced_obj_title.short_description = _("name")
    get_enhanced_obj_title.admin_order_field = "name"

    # Permissions
    # def has_view_permission(self, request, obj=None):
    #     if not self.enable_view_view:
    #         return False
    #     opts = self.opts
    #     codename = get_permission_codename('view', opts)
    #     return request.user.has_perm("%s.%s" % (opts.app_label, codename))
    #
    # def view_view(self, request, object_id, form_url='', extra_context=None):
    #     extra_context = extra_context or {}
    #     extra_context['has_add_permission'] = self.has_add_permission(request)
    #     '''
    #         Code copied from ChangeForm
    #     '''
    #
    #     to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
    #     if to_field and not self.to_field_allowed(request, to_field):
    #         raise DisallowedModelAdminToField("The field %s cannot be referenced." % to_field)
    #
    #     model = self.model
    #     opts = model._meta
    #     add = object_id is None
    #
    #     if add:
    #         if not self.has_add_permission(request):
    #             raise PermissionDenied
    #         obj = None
    #
    #     else:
    #         obj = self.get_object(request, unquote(object_id), to_field)
    #
    #         if not self.has_view_permission(request, obj):
    #             raise PermissionDenied
    #
    #         if obj is None:
    #             raise Http404(_('%(name)s object with primary key %(key)r does not exist.') % {
    #                 'name': str(opts.verbose_name), 'key': escape(object_id)})
    #
    #             # if request.method == 'POST' and "_saveasnew" in request.POST:
    #             #     return self.add_view(request, form_url=reverse('admin:%s_%s_add' % (
    #             #         opts.app_label, opts.model_name), current_app=self.admin_site.name))
    #     context = dict(self.admin_site.each_context(request),
    #                    name=obj,
    #                    app_label=opts.app_label,
    #                    object_id=object_id,
    #                    original=obj,
    #                    is_popup=(IS_POPUP_VAR in request.POST or
    #                              IS_POPUP_VAR in request.GET),
    #                    to_field=to_field,
    #                    # media=media,
    #                    preserved_filters=self.get_preserved_filters(request),
    #                    )
    #
    #     context.update(extra_context or {})
    #
    #     opts = self.model._meta
    #     app_label = opts.app_label
    #     preserved_filters = self.get_preserved_filters(request)
    #     form_url = add_preserved_filters({'preserved_filters': preserved_filters, 'opts': opts}, form_url)
    #     view_on_site_url = self.get_view_on_site_url(obj)
    #     context.update({
    #         'add': add,
    #         'change': not add,
    #         'has_add_permission': self.has_add_permission(request),
    #         'has_change_permission': self.has_change_permission(request, obj),
    #         'has_delete_permission': self.has_delete_permission(request, obj),
    #         'has_file_field': True,
    #         'has_absolute_url': view_on_site_url is not None,
    #         'absolute_url': view_on_site_url,
    #         'form_url': form_url,
    #         'opts': opts,
    #         'content_type_id': get_content_type_for_model(self.model).pk,
    #         'save_as': self.save_as,
    #         'save_on_top': self.save_on_top,
    #         'to_field_var': TO_FIELD_VAR,
    #         'is_popup_var': IS_POPUP_VAR,
    #         'app_label': app_label,
    #     })
    #
    #     request.current_app = self.admin_site.name
    #     return TemplateResponse(request, self.view_template or [
    #         "erp_framework/%s/%s/view.html" % (opts.app_label, opts.model_name),
    #         "erp_framework/%s/view.html" % opts.app_label,
    #         'erp_framework/view.html',
    #         f"{app_settings.ERP_FRAMEWORK_THEME}/view.html",
    #     ], context)

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["description"] = self.description
        return super(EntityAdmin, self).changelist_view(request, extra_context)

    def save_model(self, request, obj, form, change):
        obj.lastmod_user = request.user
        obj.lastmod_date = now()
        if not change:
            obj.owner = request.user
            obj.creation_date = now()
        super(EntityAdmin, self).save_model(request, obj, form, change)

    def get_urls(self):
        # Override ModelAdmin
        from django.urls import re_path as url

        info = self.model._meta.app_label, self.model._meta.model_name
        admin_site = self.admin_site
        reversion_urls = [
            url(
                "^recover/$",
                admin_site.admin_view(self.recoverlist_view),
                name="%s_%s_recoverlist" % info,
            ),
            url(
                "^recover/([^/]+)/$",
                admin_site.admin_view(self.recover_view),
                name="%s_%s_recover" % info,
            ),
            url(
                "^([^/]+)/history/([^/]+)/$",
                admin_site.admin_view(self.revision_view),
                name="%s_%s_revision" % info,
            ),
        ]

        urlpatterns = super(EntityAdmin, self).get_urls()

        my_urls = [
            # path('autocomplete/', wrap(self.autocomplete_view), name='%s_%s_autocomplete' % info),
            url(
                r"^slug/(?P<slug>[\w-]+)/$",
                self.admin_site.admin_view(self.get_by_slug),
                name="%s_%s_get-by-slug" % info,
            )
        ]
        return my_urls + reversion_urls + urlpatterns

    def get_by_slug(self, request, **kwargs):
        query = self.model.objects.filter(**kwargs)
        result = query.exists()
        if result:
            query = query[0]
            admin_url = reverse(
                "%s:%s_%s_change"
                % (
                    app_settings.ERP_FRAMEWORK_SITE_NAME,
                    self.model._meta.app_label,
                    self.model._meta.model_name,
                ),
                args=(query.id,),
            )
            return HttpResponseRedirect(admin_url)
        else:
            raise Http404

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.ForeignKey):
            if db_field.__class__ in self.formfield_overrides:
                kwargs = dict(self.formfield_overrides[db_field.__class__], **kwargs)

            formfield = self.formfield_for_foreignkey(db_field, request, **kwargs)
            if formfield and db_field.name not in self.raw_id_fields:
                related_modeladmin = self.admin_site._registry.get(
                    db_field.remote_field.model
                )
                wrapper_kwargs = {}
                if related_modeladmin:
                    wrapper_kwargs.update(
                        can_add_related=related_modeladmin.has_add_permission(request),
                        can_change_related=related_modeladmin.has_change_permission(
                            request
                        ),
                        can_delete_related=related_modeladmin.has_delete_permission(
                            request
                        ),
                    )
                    formfield.widget = RelatedFieldWidgetWrapper(
                        formfield.widget,
                        db_field.remote_field,
                        self.admin_site,
                        **wrapper_kwargs,
                    )
            return app_settings.ERP_ADMIN_DEFAULT_FORMFIELD_FOR_DBFIELD_FUNC(
                self, db_field, formfield, request, **kwargs
            )

        field = super(EntityAdmin, self).formfield_for_dbfield(
            db_field, request, **kwargs
        )
        if db_field.name == "slug" and self.enable_next_serial:
            field.initial = self.get_next_serial()
        elif db_field.name == "date":
            field.initial = now()
        return app_settings.ERP_ADMIN_DEFAULT_FORMFIELD_FOR_DBFIELD_FUNC(
            self, db_field, field, request, **kwargs
        )

    def get_next_serial(self):
        from erp_framework.base.helpers import get_next_serial

        return get_next_serial(self.model)

    def whole_changeform_validation(self, request, form, formsets, change, **kwargs):
        """
        A Hook for validating the whole changeform
        :param form: the ModelAdmin Form
        :param formsets: inline formsets
        :param kwargs: extra kwargs
        :return: True for valid [default] False for Invalid
        """
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

    ###
    def _changeform_view(self, request, object_id, form_url, extra_context):
        """
        A copy of original django method with 4 tricks
        1. Calls whole_changeform_validation
        2. Calls pre_save() before saving
        3. Calls post_save() after saving
        4. emits the signal changeform_saved signal

        :param request:
        :param object_id:
        :param form_url:
        :param extra_context:
        :return:
        """
        to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
        if to_field and not self.to_field_allowed(request, to_field):
            raise DisallowedModelAdminToField(
                "The field %s cannot be referenced." % to_field
            )

        model = self.model
        opts = model._meta

        if request.method == "POST" and "_saveasnew" in request.POST:
            object_id = None

        add = object_id is None

        if add:
            if not self.has_add_permission(request):
                raise PermissionDenied
            obj = None

        else:
            obj = self.get_object(request, unquote(object_id), to_field)

            if not self.has_view_or_change_permission(request, obj):
                raise PermissionDenied

            if obj is None:
                return self._get_obj_does_not_exist_redirect(request, opts, object_id)

        ModelForm = self.get_form(request, obj, change=not add)
        if request.method == "POST":
            form = ModelForm(request.POST, request.FILES, instance=obj)
            form_validated = form.is_valid()
            if form_validated:
                new_object = self.save_form(request, form, change=not add)
            else:
                new_object = form.instance
            formsets, inline_instances = self._create_formsets(
                request, new_object, change=not add
            )
            if (
                    all_valid(formsets)
                    and form_validated
                    and self.whole_changeform_validation(request, form, formsets, not add)
            ):
                self.pre_save(form, formsets, change=not add)
                self.save_model(request, new_object, form, not add)
                self.save_related(request, form, formsets, not add)
                self.post_save(request, new_object, form, formsets, not add)
                changeform_saved.send(self.model, instance=new_object, created=add)

                change_message = self.construct_change_message(
                    request, form, formsets, add
                )
                if add:
                    self.log_addition(request, new_object, change_message)
                    return self.response_add(request, new_object)
                else:
                    self.log_change(request, new_object, change_message)
                    return self.response_change(request, new_object)
            else:
                form_validated = False
        else:
            if add:
                initial = self.get_changeform_initial_data(request)
                form = ModelForm(initial=initial)
                formsets, inline_instances = self._create_formsets(
                    request, form.instance, change=False
                )
            else:
                form = ModelForm(instance=obj)
                formsets, inline_instances = self._create_formsets(
                    request, obj, change=True
                )

        if not add and not self.has_change_permission(request, obj):
            readonly_fields = flatten_fieldsets(self.get_fieldsets(request, obj))
        else:
            readonly_fields = self.get_readonly_fields(request, obj)
        adminForm = helpers.AdminForm(
            form,
            list(self.get_fieldsets(request, obj)),
            (
                # Clear prepopulated fields on a view-only form to avoid a crash.
                self.get_prepopulated_fields(request, obj)
                if add or self.has_change_permission(request, obj)
                else {}
            ),
            readonly_fields,
            model_admin=self,
        )
        media = self.media + adminForm.media

        inline_formsets = self.get_inline_formsets(
            request, formsets, inline_instances, obj
        )
        for inline_formset in inline_formsets:
            media = media + inline_formset.media

        if add:
            name = _("Add %s")
        elif self.has_change_permission(request, obj):
            name = _("Change %s")
        else:
            name = _("View %s")
        context = {
            **self.admin_site.each_context(request),
            "name": name % opts.verbose_name,
            "adminform": adminForm,
            "object_id": object_id,
            "original": obj,
            "is_popup": IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
            "to_field": to_field,
            "media": media,
            "inline_admin_formsets": inline_formsets,
            "errors": helpers.AdminErrorList(form, formsets),
            "preserved_filters": self.get_preserved_filters(request),
        }

        # Hide the "Save" and "Save and continue" buttons if "Save as New" was
        # previously chosen to prevent the interface from getting confusing.
        if (
                request.method == "POST"
                and not form_validated
                and "_saveasnew" in request.POST
        ):
            context["show_save"] = False
            context["show_save_and_continue"] = False
            # Use the change template instead of the add template.
            add = False

        context.update(extra_context or {})

        return self.render_change_form(
            request, context, add=add, change=not add, obj=obj, form_url=form_url
        )

    def get_actions(self, request):
        actions = super(EntityAdmin, self).get_actions(request)
        if not (
                app_settings.ERP_FRAMEWORK_ENABLE_ADMIN_DELETE_ALL
                and request.user.is_superuser
        ):
            if "delete_selected" in actions:
                del actions["delete_selected"]
        return actions

    def get_list_display(self, request):
        list_display = super(EntityAdmin, self).get_list_display(request)

        if self.has_view_permission(request):
            list_display = ("get_stats_icon",) + list_display

        return list_display


class TransactionAdmin(EntityAdmin):
    enable_view_view = False
    list_per_page = 50
    view_on_site = False
    list_display = ("slug", "date", "value", "get_history_link")
    list_display_links = ("slug", "date")
    fields = (("slug", "date"),)
    exclude = ("type",)
    formfield_overrides = {}
    date_hierarchy = "date"
    type = None

    # Copy values from parent model to child inline models,
    # If `all-fk` then automatically it will copy all foreign keys included in the fields of the add/change Form
    # other options are None , or a list of field names
    copy_to_inlines = "all-fk"

    copy_form_notes_to_formset = False
    search_fields = ["date", "slug"]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        form_field = super(TransactionAdmin, self).formfield_for_dbfield(
            db_field, request, **kwargs
        )
        form_field = app_settings.ERP_ADMIN_DEFAULT_FORMFIELD_FOR_DBFIELD_FUNC(
            self, db_field, form_field, request, **kwargs
        )
        return form_field

    def get_foreign_keys(self, form_fields=None):
        fks = [
            field.name
            for field in self.model._meta.get_fields(include_parents=False)
            if field.get_internal_type() == "ForeignKey"
        ]
        if form_fields:
            fks = set(fks).intersection(set(form_fields))
        return fks

    def get_copy_to_inlines(self, form, formset):
        if self.copy_to_inlines == "all-fk":
            fks = self.get_foreign_keys(form.fields.keys())
            return fks
        return self.copy_to_inlines or []

    def get_list_filter(self, request):
        list_filter = super().get_list_filter(request)
        if not list_filter:
            return self.get_foreign_keys(flatten_list(self.get_fields(request)))
        return list_filter

    def save_formset(self, request, form, formset, change):
        copy_to_inlines = self.get_copy_to_inlines(form, formset)
        for formset_form in formset:
            formset_form.instance.date = form.instance.date
            formset_form.instance.type = form.instance.type
            formset_form.instance.slug = form.instance.slug
            formset_form.instance.lastmod_user = request.user
            if self.copy_form_notes_to_formset:
                formset_form.instance.notes = form.instance.notes
            for copy_item in copy_to_inlines:
                formset_form.instance.__setattr__(
                    copy_item, form.instance.__getattribute__(copy_item)
                )
                # print(copy_item, form.instance.__getattribute__(copy_item))
            if formset_form.instance.pk is not None:
                formset_form.instance.save()
        formset.save()


class TransactionItemAdmin(admin.TabularInline):
    template = f"{app_settings.ERP_FRAMEWORK_THEME}/edit_inline/tabular.html"
    extra = 2
    exclude = (
        "slug",
        "date",
        "type",
        "lastmod",
        "lastmod_user",
        "owner",
        "creation_date",
    )
    formfield_overrides = {
        models.TextField: {"widget": TextInput},
        DecimalField: {"widget": NumberInput},
        # ForeignKey: {'widget': RaBootstrapForeignKeyWidget},
    }
    view_on_site = False

    """
    To simplify complex forms with inline , making inline permission reflect base form permission
    permission_override_model can be True, False , str Or ModelBase
    """
    permission_override_model = True

    def get_ra_permission_codename(self, action, model_name):
        """
        Returns the codename of the permission for the specified action.
        """
        return "%s_%s" % (action, model_name)

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
                "self.permission_override_model can be True, False , str or ModelBase"
                " .Got %s instead "
                % type(self.permission_override_model)
            )

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
            codename = self.get_ra_permission_codename("add", model_name)
        else:
            codename = get_permission_codename("add", opts)
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
            codename = self.get_ra_permission_codename("change", model_name)
        else:
            codename = get_permission_codename("change", opts)
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
            codename = self.get_ra_permission_codename("delete", model_name)
        else:
            codename = get_permission_codename("delete", opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.ForeignKey):
            if db_field.__class__ in self.formfield_overrides:
                kwargs = dict(self.formfield_overrides[db_field.__class__], **kwargs)

            formfield = self.formfield_for_foreignkey(db_field, request, **kwargs)
            if formfield and db_field.name not in self.raw_id_fields:
                related_modeladmin = self.admin_site._registry.get(
                    db_field.remote_field.model
                )
                wrapper_kwargs = {}
                if related_modeladmin:
                    wrapper_kwargs.update(
                        can_add_related=related_modeladmin.has_add_permission(request),
                        can_change_related=related_modeladmin.has_change_permission(
                            request
                        ),
                        can_delete_related=related_modeladmin.has_delete_permission(
                            request
                        ),
                    )
                    formfield.widget = RelatedFieldWidgetWrapper(
                        formfield.widget,
                        db_field.remote_field,
                        self.admin_site,
                        **wrapper_kwargs,
                    )
        form_field = super(TransactionItemAdmin, self).formfield_for_dbfield(
            db_field, request, **kwargs
        )
        form_field = app_settings.ERP_ADMIN_DEFAULT_FORMFIELD_FOR_DBFIELD_FUNC(
            self, db_field, form_field, request, **kwargs
        )
        return form_field


class RaGenericTabularInline(GenericTabularInline):
    """
    Implementation of teh needed methods for Generic Tabular inline with RA
    """

    extra = 1
    exclude = (
        "slug",
        "date",
        "type",
        "lastmod",
        "lastmod_user",
        "owner",
        "creation_date",
    )
    formfield_overrides = {
        TextField: {"widget": TextInput},
        DecimalField: {"widget": NumberInput},
    }
    view_on_site = False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.ForeignKey):
            if db_field.__class__ in self.formfield_overrides:
                kwargs = dict(self.formfield_overrides[db_field.__class__], **kwargs)

            formfield = self.formfield_for_foreignkey(db_field, request, **kwargs)
            if formfield and db_field.name not in self.raw_id_fields:
                related_modeladmin = self.admin_site._registry.get(
                    db_field.remote_field.model
                )
                wrapper_kwargs = {}
                if related_modeladmin:
                    wrapper_kwargs.update(
                        can_add_related=related_modeladmin.has_add_permission(request),
                        can_change_related=related_modeladmin.has_change_permission(
                            request
                        ),
                        can_delete_related=related_modeladmin.has_delete_permission(
                            request
                        ),
                    )
                    formfield.widget = RelatedFieldWidgetWrapper(
                        formfield.widget,
                        db_field.remote_field,
                        self.admin_site,
                        **wrapper_kwargs,
                    )
        form_field = super(RaGenericTabularInline, self).formfield_for_dbfield(
            db_field, request, **kwargs
        )
        form_field = app_settings.ERP_ADMIN_DEFAULT_FORMFIELD_FOR_DBFIELD_FUNC(
            self, db_field, form_field, request, **kwargs
        )
        return form_field


class PrepopulatedAdmin(object):
    prepopulation_querysets = None
    prepopulation_fields = None
    prepopulation_fields_from = None
    prepopulated_inlines = []  # a subset of inlines that will be prepopulated
    prepopulation_extra_data = None  # to do A list of fields

    def add_view(self, request, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["prepopulation_fields"] = self.prepopulation_fields
        return super(PrepopulatedAdmin, self).add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["prepopulation_fields"] = self.prepopulation_fields
        return super(PrepopulatedAdmin, self).change_view(
            request, object_id, form_url, extra_context
        )

    def get_prepopulattion_queryset(self, inline):
        return self.prepopulation_querysets.get(inline.__class__, None)

    def get_prepopulation_queryset(self, inline, inline_queryset, request, obj, change):
        """
        return a queryset Or None
        """
        try:
            return self.prepopulation_querysets.get(inline.__class__, None)
        except AttributeError:
            raise ImproperlyConfigured(
                "Please check %s.prepopulation_querysets to be a dict type"
                % self.__class__
            )

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
        return ""

    def get_prepopulation_extra_data(self, inline, data):
        """
        Hook to add Extra data (other then prepoputation field) to the prepopulated form
        """
        return {}

    def get_formset_initial(self, inline, inline_queryset, request, obj, change):
        self.prepopulation_fields_from = self.prepopulation_fields_from or {}

        prepopulateion_queryset = self.get_prepopulation_queryset(
            inline, inline_queryset, request, obj, change
        )
        prepopulation_field = self.prepopulation_fields.get(inline.__class__, None)
        prepopulation_field_from = self.prepopulation_fields_from.get(
            inline.__class__, "id"
        )
        prepopulation_field_from = (
            prepopulation_field_from
            if prepopulation_field_from == "id"
            else "%s_id" % prepopulation_field_from
        )

        if prepopulateion_queryset is None:
            return []
        else:
            assert prepopulation_field is not None
            initial_data = prepopulateion_queryset.values(prepopulation_field_from)

            id_list = [x[prepopulation_field_from] for x in initial_data]
            initial_data = [x for x in initial_data]
            return_data = []
            if change:
                filtered_queryset = self.filter_inline_queryset(
                    inline_queryset, request, obj, change
                )
                for item in filtered_queryset:
                    try:
                        x = id_list.index(
                            item.__getattribute__("%s_id" % prepopulation_field)
                        )
                        id_list.pop(x)
                        initial_data.pop(x)
                    except ValueError:
                        pass
                for i, data in enumerate(initial_data):
                    return_data.append(
                        {prepopulation_field: initial_data[i][prepopulation_field_from]}
                    )
                request._initial_data = return_data
                return return_data

            elif not change:
                ret_val = []
                for item in initial_data:
                    ret_val.append(
                        {prepopulation_field: item[prepopulation_field_from]}
                    )
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
                "instance": obj,
                "prefix": prefix,
                "queryset": inline_queryset,
            }
            if request.method == "POST":
                formset_params.update(
                    {
                        "data": request.POST,
                        "files": request.FILES,
                        "save_as_new": "_saveasnew" in request.POST,
                    }
                )
            else:
                initial_data = self.get_formset_initial(
                    inline, inline_queryset, request, obj, change
                )
                # Not here is a necessity, in case you find unuseful revise again
                if (
                        inline.__class__ in self.prepopulated_inlines
                        or not self.prepopulated_inlines
                ):
                    FormSet.extra = len(initial_data)
                if initial_data:
                    formset_params.update({"initial": initial_data})
            formsets.append(FormSet(**formset_params))
            inline_instances.append(inline)
        return formsets, inline_instances


class RaPrePopulatedAdmin(PrepopulatedAdmin, EntityAdmin):
    pass


class RaMovementPrepopulatedAdmin(RaPrePopulatedAdmin):
    enable_view_view = False
    list_per_page = 50
    copy_to_inlines = []
    copy_form_notes_to_formset = False

    def save_formset(self, request, form, formset, change):
        for formset_form in formset:
            formset_form.instance.date = form.instance.date
            formset_form.instance.type = form.instance.type
            formset_form.instance.slug = form.instance.slug
            formset_form.instance.lastmod_user = request.user
            if self.copy_form_notes_to_formset:
                formset_form.instance.notes = form.instance.notes
            for copy_item in self.copy_to_inlines:
                formset_form.instance.__setattr__(
                    copy_item, form.instance.__getattribute__(copy_item)
                )

        formset.save()

# class RaUserAdmin(RaThemeMixin, UserTabularPermissionsMixin, UserAdmin):
#     enable_view_view = False
#     date_hierarchy = None
#     fields = None
#     list_display_links = ["username"]
#     change_user_password_template = (
#         f"{app_settings.ERP_FRAMEWORK_THEME}/auth/user/change_password.html"
#     )
#     list_display = ("username", "is_superuser", "last_login", "is_active")
#
#     save_on_top = True
#
#     fieldsets = (
#         (None, {"fields": ("username", "password")}),
#         (_("Personal info"), {"fields": (("first_name", "last_name", "email"),)}),
#         (
#             _("Permissions"),
#             {"fields": (("is_active", "is_superuser"), "groups", "user_permissions")},
#         ),
#         # (_('Important dates'), {'fields': (('last_login', 'date_joined'),)}),
#     )
#     list_filter = ("is_superuser", "is_active", "groups")
#     form = CustomUserChangeForm
#
#     def get_actions(self, request):
#         actions = super(RaUserAdmin, self).get_actions(request)
#         if "delete_selected" in actions:
#             del actions["delete_selected"]
#         return actions
#
#     def has_delete_permission(self, request, obj=None):
#         return False
#
#     def save_model(self, request, obj, form, change):
#         obj.is_staff = True
#         super(RaUserAdmin, self).save_model(request, obj, form, change)
#
#     def get_inline_instances(self, request, obj=None):
#         if obj is None:
#             return []
#         return super(RaUserAdmin, self).get_inline_instances(request, obj)
#
#     def changelist_view(self, request, extra_context=None):
#         extra_context = {"has_detached_sidebar": True}
#         return super(RaUserAdmin, self).changelist_view(request, extra_context)
#
#
# class RaGroupAdmin(RaThemeMixin, GroupTabularPermissionsMixin, GroupAdmin):
#     enable_view_view = False
#     date_hierarchy = None
#     fields = None
#     list_display_links = ["name"]
#     list_display = ["name"]
#
#     save_on_top = True
#
#
#
# erp_admin_site.register(Group, RaGroupAdmin)
# erp_admin_site.register(User, RaUserAdmin)

from django.contrib import admin
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.template.defaultfilters import dictsort, capfirst, truncatewords
from django.urls import reverse, NoReverseMatch
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from erp_framework.activity.models import MyActivity
from erp_framework.admin.admin import erp_admin_site, RaThemeMixin
from erp_framework.base import app_settings
from erp_framework.base.helpers import RaPermissionWidgetExclude

action_names = {
    ADDITION: 'Addition',
    CHANGE: 'Change',
    DELETION: 'Deletion',
}


def translate_list(l, func=_):
    """
    Translate strings in list, used originally to translate report_columns
    :param l: list of data
    :param func: translation function
    :return: translated list
    """
    t = []
    for i in l:
        t.append(func(i))
    return t


class FilterBase(admin.SimpleListFilter):
    def queryset(self, request, queryset):
        if self.value():
            dictionary = dict(((self.parameter_name, self.value()),))
            return queryset.filter(**dictionary)


class ActionFilter(FilterBase):
    title = _('Action')
    parameter_name = 'action_flag'

    def lookups(self, request, model_admin):
        vals = ()
        for x in action_names.items():
            verbose = x[1] if x[1] != 'Change' else 'Update'
            vals += ((x[0], _(verbose)),)
        return vals


class UserFilter(FilterBase):
    """Use this filter to only show current users, who appear in the log."""
    title = _('User')
    parameter_name = 'user_id'

    def lookups(self, request, model_admin):
        return tuple((u.id, u.username)
                     for u in User.objects.filter(pk__in=LogEntry.objects.values_list('user_id').distinct())
                     )


class AdminFilter(UserFilter):
    """Use this filter to only show current Superusers."""
    title = 'admin'

    def lookups(self, request, model_admin):
        return tuple((u.id, u.username) for u in User.objects.filter(is_superuser=True))


class StaffFilter(UserFilter):
    """Use this filter to only show current Staff members."""
    title = 'staff'

    def lookups(self, request, model_admin):
        return tuple((u.id, u.username) for u in User.objects.filter(is_staff=True))


class RAContentTypeFilter(admin.SimpleListFilter):
    """Use this filter to only Appropriate content types."""
    title = _('Content Type')
    parameter_name = 'content_type'

    def lookups(self, request, model_admin):
        vals = ()
        val_list = []
        cs = ContentType.objects.filter(logentry__action_flag__in=[1, 2, 3]).distinct()
        exclude_function = RaPermissionWidgetExclude()
        for c in cs:
            model = c.model_class()
            if model:
                if not exclude_function(model):
                    val_list.append({
                        'name': capfirst(str(model._meta.verbose_name_plural)),
                        'value': ((c.pk, capfirst(str(model._meta.verbose_name_plural))),)
                    })
        ordered_list = dictsort(val_list, 'name')
        for o in ordered_list:
            vals += o['value']
        return vals

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(content_type_id=self.value())
        return queryset
        # return tuple((u.id, u.username) for u in User.objects.filter(is_staff=True))


class LogEntryAdmin(RaThemeMixin, admin.ModelAdmin):
    date_hierarchy = 'action_time'
    actions = None
    list_display_links = None
    # readonly_fields = LogEntry._meta.get_all_field_names()
    readonly_fields = [f.name for f in LogEntry._meta.get_fields()]

    list_filter = [
        UserFilter,
        ActionFilter,
        RAContentTypeFilter,
        # 'content_type',
        # 'user',
    ]

    search_fields = [
        'object_repr',
        'change_message'
    ]

    list_display = [
        'action_time',
        'get_user',
        'action_description',
        'get_contenttype',
        'object_link',
        # 'action_flag',
        'get_change_message',
        'review'
    ]

    def has_module_permission(self, request):
        return True

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True and request.method != 'POST'

    def has_delete_permission(self, request, obj=None):
        return False

    def get_user(self, obj):
        return obj.user

    get_user.short_description = _('User')
    get_user.admin_order_field = 'user'

    def get_change_message(self, obj):
        return truncatewords(obj.get_change_message(), 23)

    get_change_message.short_description = _('Comment')

    def object_link(self, obj):
        ct = obj.content_type
        repr_ = escape(obj.object_repr)
        try:
            href = reverse('%s:%s_%s_change' % (app_settings.RA_ADMIN_SITE_NAME, ct.app_label, ct.model),
                           args=[obj.object_id])
            link = u'<a href="%s">%s</a>' % (href, repr_)
        except NoReverseMatch:
            link = repr_
        return mark_safe(link) if obj.action_flag != DELETION else repr_

    object_link.allow_tags = True
    object_link.admin_order_field = 'object_repr'
    object_link.short_description = _('Slug/Name')

    def get_queryset(self, request):
        queryset = super(LogEntryAdmin, self).get_queryset(request) \
            .prefetch_related('content_type')
        if not request.user.is_superuser:
            queryset = queryset.filter(user__id=request.user.pk)
        return queryset

    def get_list_filter(self, request):
        filters = super(LogEntryAdmin, self).get_list_filter(request)
        if not request.user.is_superuser:
            filters.pop(0)
        return filters

    def action_description(self, obj):
        verbose = action_names[obj.action_flag]
        # verbose = 'Update' if verbose == 'Change' else verbose

        return _(verbose)

    action_description.short_description = _('Action')
    action_description.admin_order_field = 'action_flag'

    def get_contenttype(self, obj):
        return capfirst(obj.content_type)

    get_contenttype.short_description = _('Content Type')
    get_contenttype.admin_order_field = 'content_type__model'

    def review(self, obj):
        if obj.action_flag == 2:
            try:
                url = reverse('%s:%s_%s_history' % (app_settings.RA_ADMIN_SITE_NAME, obj.content_type.app_label,
                                                    obj.content_type.model), args=(obj.object_id,))
            except NoReverseMatch:
                url = ''
            link = """<a href="%s" class="legitRipple" data-popup="tooltip" title="%s">
                <i class="fas fa-history text-indigo-800"></i>
                <span class="legitRipple-ripple"></span></a>""" % (url, _('History'))
            return mark_safe(link)
        elif obj.action_flag == 3:
            url = reverse('%s:%s_%s_recover' % (app_settings.RA_ADMIN_SITE_NAME, obj.content_type.app_label,
                                                obj.content_type.model), args=(obj.object_id,))
            link = """<a href="%s" class="legitRipple" data-popup="tooltip" title="%s">
                    <i class="fas fa-undo text-indigo-800"></i>
                    <span class="legitRipple-ripple"></span></a>""" % (url, _('Recover'))
            return mark_safe(link)

        return ''

    review.short_description = _('review')

    def changelist_view(self, request, extra_context=None):
        extra_context = {
            'has_detached_sidebar': True
        }
        return super(LogEntryAdmin, self).changelist_view(request, extra_context)


class MyActivityAdmin(LogEntryAdmin):
    list_filter = [

        ActionFilter,
        RAContentTypeFilter,
    ]

    def get_queryset(self, request):
        qs = super(MyActivityAdmin, self).get_queryset(request)
        qs = qs.filter(user_id=request.user.pk)
        return qs


# erp_admin_site.register(LogEntry, LogEntryAdmin)

erp_admin_site.register(MyActivity, MyActivityAdmin)

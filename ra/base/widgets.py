from __future__ import absolute_import

from django import forms
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.forms import TextInput, SplitDateTimeWidget
from django.forms.utils import flatatt
from django.template.defaultfilters import capfirst
from django.utils.encoding import force_text
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from ra.base.cache import get_cached_slug, get_cached_name


class AdminSplitDateTimeNoBr(forms.SplitDateTimeWidget):
    pass


class RaRelatedFieldWidgetWrapper(RelatedFieldWidgetWrapper):
    pass


class RaBootstrapForeignKeyWidget(TextInput):
    is_read_only = False

    class Media:
        css = dict(all=('ra/css/ra_foreignkey_widget.css',))

    def __init__(self, attrs=None, model_name=None, id_container=None, allow_multi=False, autocomplete_endpoint=None):
        super(RaBootstrapForeignKeyWidget, self).__init__(attrs)
        self.model_name = model_name
        self.id_container = id_container
        self.allow_multi = allow_multi
        self.autocomplete_endpoint = autocomplete_endpoint or model_name

    def get_title(self, model_name, value, model_klass):
        from ra.utils.views import get_linkable_slug_title
        # if model_klass is None:

        title = ''
        if value != '' and value is not None:
            # Only add the 'value' attribute if a value is non-empty.
            if type(value) is list:
                if len(value) >= 1:
                    value = value[0]

            if type(value) is not int:
                if len(value.split(',')) > 1:
                    title = _('choice been made')
                    # multi value
            if title == '':
                title = get_cached_name(model_name, value, model_class=model_klass)
                title = get_linkable_slug_title(model_name, value, title, True)
        return mark_safe(title)

    def get_context(self, name, value, attrs):

        context = super(RaBootstrapForeignKeyWidget, self).get_context(name, value, attrs)
        model_klass = None

        if self.model_name is None:
            self.model_name = self.choices.queryset.model.__name__.lower()
            model_klass = self.choices.queryset.model
        model_name = self.model_name

        context['model_name'] = self.model_name
        context['endpoint'] = self.autocomplete_endpoint or self.model_name

        context['title'] = self.get_title(model_name, value, model_klass)

        context['slug'] = get_cached_slug(model_name, value) if value else ''

        context['slug_attrs'] = self.get_slug_attrs(model_name, {})
        context['my_value'] = value
        context['choose_label'] = capfirst(_('choose'))
        context['multi_select'] = self.allow_multi

        return context

    def get_related_attrs(self, final_attrs):
        attrs = flatatt(final_attrs)

    def __render(self, name, value, attrs=None):
        from ra.utils.views import get_linkable_slug_title

        if self.model_name is None:
            self.model_name = self.choices.queryset.model.__name__.lower()
        # else:
        model_name = self.model_name
        endpoint = self.autocomplete_endpoint or model_name
        title = ''
        # print name

        if value is None:
            value = ''
        final_attrs = self.build_attrs(attrs)
        final_attrs['style'] = 'Display: None'
        final_attrs['class'] = 'ra-foreignkey-widget-pk'
        # print final_attrs
        if value != '':
            # Only add the 'value' attribute if a value is non-empty.
            if type(value) is list:
                if len(value) >= 1:
                    value = value[0]
            final_attrs['value'] = force_text(self._format_value(value))

            if type(value) is not int:
                if len(value.split(',')) > 1:
                    title = _('choice been made')
                    # multi value
            if title == '':
                slug = get_cached_slug(model_name, value)
                title = get_cached_name(model_name, value)
                # title = get_decorated_title(slug, '%s__title' % model_name, title, None, new_page=True,
                #                             use_push_dtate=False)
                title = get_linkable_slug_title(model_name, value, title, True)
        # try:
        origial_render = format_html('<input{0} />', flatatt(final_attrs))
        # print self.render_slug(name , value , attrs)
        slug_sender = self.render_slug(name, value, attrs)
        value_dict = {'id_container': origial_render, 'slug_container': slug_sender, 'title_container': title,
                      'model_name': self.model_name.strip(), 'endpoint': endpoint}
        if self.allow_multi:
            value_dict['choose_label'] = capfirst(_('choose'))
            final_value = self.get_multiSelector() % value_dict
        else:
            final_value = self.get_postfixHTML() % value_dict
        # except Exception as e:
        #     print 'Error in Widgets'
        #     print e
        #     traceback.print_exc(file=sys.stdout)

        return format_html(final_value)

    def get_slug_attrs(self, model_name, attrs):
        attrs = attrs or {}
        endpoint = self.autocomplete_endpoint or model_name
        final_attrs = {
            'class': 'form-control ra-foreignkey-widget-slug %s' % model_name
        }
        final_attrs['keepcloseeye'] = True
        if 'ra_url_factory' in attrs:
            final_attrs['ra_url_factory'] = attrs['ra_url_factory']

        if 'ra_autocomplete_response_handler' in attrs:
            final_attrs['ra_autocomplete_response_handler'] = attrs['ra_autocomplete_response_handler']

        final_attrs.pop('style', False)
        if self.is_read_only:
            final_attrs['style'] = 'Display: None'
        final_attrs['ra_autocomplete_bind'] = 'true'
        final_attrs['ra_autocomplete_model'] = endpoint
        if self.id_container:
            final_attrs['ra_autocomplete_id_container'] = '#id_' + self.id_container
        else:
            final_attrs['ra_autocomplete_id_container'] = '#id_' + model_name

        final_attrs['id'] = 'id_%s__slug' % model_name
        final_attrs['data-name'] = '%s__slug' % model_name
        final_attrs['title_container'] = '#%s__title' % model_name
        final_attrs['type'] = 'text'
        return final_attrs

    def render_slug(self, name, value, attrs=None):

        model_name = self.model_name
        endpoint = self.autocomplete_endpoint or model_name

        # print attrs

        if value is None:
            value = ''
        final_attrs = {
            'class': 'form-control ra-foreignkey-widget-slug %s' % model_name}  # self.build_attrs(attrs, type=self.input_type, name=name)
        # print 'final attrs %s' % final_attrs

        if 'keepcloseeye' in attrs:
            final_attrs['keepcloseeye'] = True
        attrs = self.build_attrs(attrs)
        if 'ra_url_factory' in attrs:
            final_attrs['ra_url_factory'] = attrs['ra_url_factory']

        if 'ra_autocomplete_response_handler' in attrs:
            final_attrs['ra_autocomplete_response_handler'] = attrs['ra_autocomplete_response_handler']

        final_attrs.pop('style', False)
        if self.is_read_only:
            final_attrs['style'] = 'Display: None'
        final_attrs['ra_autocomplete_bind'] = 'true'
        final_attrs['ra_autocomplete_model'] = endpoint
        if self.id_container:
            final_attrs['ra_autocomplete_id_container'] = '#id_' + self.id_container
        else:
            final_attrs['ra_autocomplete_id_container'] = '#id_' + name

        final_attrs['id'] = 'id_%s__slug' % name
        final_attrs['data-name'] = '%s__slug' % name
        final_attrs['title_container'] = '#%s__title' % model_name
        final_attrs['type'] = 'text'
        # print final_attrs
        if value != '':
            # Only add the 'value' attribute if a value is non-empty.
            id = force_text(self._format_value(value))
            if len(id.split(',')) > 1:
                """matrix support case"""
                final_attrs['disabled'] = 'disabled'
            else:
                slug = get_cached_slug(model_name, value)
                # title = get_cached_name(model_name,value)
                # print 'id:%s slug: %s , title: %s' % (value,slug,title)
                final_attrs.update(self.get_extra_attrs(value))
                final_attrs['value'] = slug
                # final_attrs['ra_autocomplete_default_name'] = title
        ret_val = format_html('<input{0} />', flatatt(final_attrs))
        return ret_val

    def get_extra_attrs(self, value):
        return []

    def get_postfixHTML(self):
        html = '<div class="input-group ra-input-group ra-foreignkey-widget"> \
            %(id_container)s \
            %(slug_container)s \
              <span class="input-group-addon ra-input-group-addon ra_title ra-foreignkey-widget-title"><span id="id_%(model_name)s__title" name="%(model_name)s__title">%(title_container)s</span></span>\
      </div>'
        return html

    def get_multiSelector(self):
        html = '<div class="input-group ra-input-group ra-foreignkey-widget"> \
        %(id_container)s \
        %(slug_container)s \
          <span class="input-group-addon ra-input-group-addon ra_title ra-foreignkey-widget-title"><span id="id_%(model_name)s__title" name="%(model_name)s__title">%(title_container)s</span></span>\
          <span class="input-group-addon ra-input-group-addon ra_multi_selector ra-foreignkey-widget-multiSelector">' \
               '<a data-reveal-id="overlay_modal" ra_model="%(model_name)s" href="#">%(choose_label)s</a></span>\
      </div>'

        return html


class RaBootstrapDateTime(SplitDateTimeWidget):
    def render(self, name, value, attrs=None, renderer=None):
        if self.is_localized:
            for widget in self.widgets:
                widget.is_localized = self.is_localized
        # value is a list of values, each corresponding to a widget
        # in self.widgets.
        if not isinstance(value, list):
            value = self.decompress(value)
        output = []
        final_attrs = self.build_attrs(attrs)
        id_ = final_attrs.get('id', None)
        for i, widget in enumerate(self.widgets):
            try:
                widget_value = value[i]
            except IndexError:
                widget_value = None
            if id_:
                final_attrs = dict(final_attrs, id='%s_%s' % (id_, i))
            output.append(widget.render(name + '_%s' % i, widget_value, final_attrs))
        return_html = self.get_foundation_structure() % {'datewidget': output[0], 'timewidget': output[1]}
        return mark_safe(return_html)

    def get_foundation_structure(self):
        html = '<div class="row"> \
          <div class="col-sm-6"> \
          %(datewidget)s \
          </div>\
          <div class="col-sm-6"> \
            %(timewidget)s \
          </div>\
        </div>'

        return html

from __future__ import absolute_import

from django import forms
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.forms import SplitDateTimeWidget
from django.utils.safestring import mark_safe


class AdminSplitDateTimeNoBr(forms.SplitDateTimeWidget):
    pass


class RaRelatedFieldWidgetWrapper(RelatedFieldWidgetWrapper):
    pass





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

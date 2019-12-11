from __future__ import unicode_literals
import datetime
from django import forms
from django.utils.timezone import now
import pytz
from ra.base.app_settings import DEFAULT_FROM_DATE_TIME
from ra.reporting.form_fields import RaDateDateTimeField
from ra.base.widgets import RaBootstrapDateTime
from django.utils.translation import ugettext_lazy as _
from django.forms.utils import ErrorList


class OrderByForm(forms.Form):
    order_by = forms.CharField(required=False)

    def get_order_by(self, default_field=None):
        """
        Get the order by specified by teh form or the default field if provided
        :param default_field:
        :return: tuple of field and direction
        """
        if self.is_valid():
            order_field = self.cleaned_data['order_by']
            order_field = order_field or default_field
            if order_field:
                return self.parse_order_by_field(order_field)
        return None, None

    def parse_order_by_field(self, order_field):
        """
        Specify the field and direction
        :param order_field: the field to order by
        :return: tuple of field and direction
        """
        if order_field:
            asc = True
            if order_field[0:1] == '-':
                order_field = order_field[1:]
                asc = False
            return order_field, not asc
        return None, None


class SimpleReportForm(forms.Form):
    doc_date = forms.DateField(input_formats=["%Y-%m-%d"], required=False, label=_('at date'))

    from_doc_date = RaDateDateTimeField(required=False, label=_('from date'),
                                        initial=DEFAULT_FROM_DATE_TIME,
                                        widget=RaBootstrapDateTime(),
                                        input_date_formats=['%Y-%m-%d', '%Y-%m-%d'],
                                        input_time_formats=['%H:%M', '%H:%M:%S'])

    to_date_initial = datetime.datetime.combine(now().date(), datetime.time.max)
    to_doc_date = RaDateDateTimeField(required=False, initial=to_date_initial,
                                      label=_('to date'), widget=RaBootstrapDateTime(),
                                      input_date_formats=['%Y-%m-%d', '%Y-%m-%d'],
                                      input_time_formats=['%H:%M', '%H:%M:%S'])

    def get_queryset_filters(self, w_date=False):
        """
        Return a dict that represents filter on the form
        :param w_date:
        :param w_doc_types:
        :return:
        """
        _values = {}
        doc_date = self.cleaned_data['doc_date']
        try:
            doc_date = doc_date.strftime('%Y-%m-%d')
        except:
            doc_date = None

        if doc_date:
            date_1 = pytz.utc.localize(
                datetime.datetime.combine(self.cleaned_data['doc_date'], datetime.datetime.min.time()))

            date_2 = date_1 + datetime.timedelta(days=1)
            # _values['doc_date__gt'] = date_1
            self.cleaned_data['from_doc_date'] = date_1
            # _values['doc_date__lte'] = date_2
            self.cleaned_data['to_doc_date'] = date_2

        if w_date:
            _values['doc_date__gt'] = self.get_from_doc_date()
            _values['doc_date__lte'] = self.get_to_doc_date()

        return _values

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None, initial=None, error_class=ErrorList,
                 label_suffix=None, empty_permitted=False, **kwargs):
        super(SimpleReportForm, self).__init__(data, files, auto_id, prefix, initial, error_class, label_suffix,
                                               empty_permitted)

    @property
    def _fkeys(self):
        return []

    def get_from_doc_date(self):
        return self.cleaned_data.get('from_doc_date') or DEFAULT_FROM_DATE_TIME

    def get_to_doc_date(self):
        x = now()
        return self.cleaned_data.get('to_doc_date') or x.combine(x, x.time().max)

    def is_time_series(self, *args, **kwargs):
        return False

    def is_matrix_support(self, *args, **kwargs):
        return False


class ReportFormWithSeries(SimpleReportForm):
    time_series_pattern = forms.CharField()

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None, initial=None, error_class=ErrorList,
                 label_suffix=None, empty_permitted=False, **kwargs):
        super(ReportFormWithSeries, self).__init__(data, files, auto_id, prefix, initial, error_class, label_suffix,
                                                   empty_permitted, **kwargs)
        self.fields['time_series_pattern'].wiget = forms.Select(choices=(('none', _('None')), ('daily', _('Daily')),
                                                                         ('monthly', _('Monthly'))))

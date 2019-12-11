from __future__ import unicode_literals
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.forms import UserChangeForm
from django import forms
from ra.base.helpers import get_ra_relevant_content_types


class RaUserChangeForm(UserChangeForm):
    def __init__(self, *args, **kwargs):
        super(RaUserChangeForm, self).__init__(*args, **kwargs)
        self.fields['password'].help_text = '<a class="reset-password" href=\"../password/\">%s</a>' % _(
            'Reset password here')


class CtCheckForm(forms.Form):
    content_type = forms.ChoiceField(choices=(), widget=forms.Select(), label=_('content type'))
    object_slug = forms.CharField(max_length=300, label=_('slug'))

    def __init__(self, *args, **kwargs):
        self.base_fields['content_type'] = forms.ChoiceField(choices=get_ra_relevant_content_types(),
                                                             widget=forms.Select())
        super(CtCheckForm, self).__init__(*args, **kwargs)

    def clean_content_type(self):
        pk = self.cleaned_data['content_type']
        return ContentType.objects.get_for_id(pk)


class CtReverseCheckForm(forms.Form):
    content_type = forms.ChoiceField(choices=(), widget=forms.Select(), label=_('content type'))
    object_id = forms.IntegerField()

    def __init__(self, *args, **kwargs):
        self.base_fields['content_type'] = forms.ChoiceField(choices=get_ra_relevant_content_types(),
                                                             widget=forms.Select())
        super(CtReverseCheckForm, self).__init__(*args, **kwargs)

    def clean_content_type(self):
        pk = self.cleaned_data['content_type']
        return ContentType.objects.get_for_id(pk)

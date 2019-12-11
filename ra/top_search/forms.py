from __future__ import unicode_literals
from django import forms


class SearchForm(forms.Form):
    q = forms.CharField(required=True)

from __future__ import unicode_literals
from django import forms

class RaDateDateTimeField(forms.SplitDateTimeField):
    """
    Make sure to translate arabic numbers to western numbers so
    default operation can carry on smoothly.
    """

    def clean(self, value):
        from ra.utils.views import easter_western_map
        new_value = []
        for i in value:
            if type(i) in [str]:
                new_value.append(i.translate(easter_western_map))
            else:
                new_value.append(i)
        return super(RaDateDateTimeField, self).clean(new_value)

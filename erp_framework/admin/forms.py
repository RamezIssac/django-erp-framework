from __future__ import unicode_literals

from django.contrib.auth.forms import UserChangeForm
from django.utils.translation import gettext_lazy as _


class CustomUserChangeForm(UserChangeForm):
    def __init__(self, *args, **kwargs):
        super(CustomUserChangeForm, self).__init__(*args, **kwargs)
        self.fields[
            "password"
        ].help_text = '<a class="reset-password" href="../password/">%s</a>' % _(
            "Reset password here"
        )

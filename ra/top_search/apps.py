from __future__ import unicode_literals
from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class SearchConfig(AppConfig):
    name = 'ra.top_search'
    verbose_name = _('Top Search')

    # def ready(self):
    #     super(StoreConfig, self).ready()
    #     import report_views
    #     import ra_conf

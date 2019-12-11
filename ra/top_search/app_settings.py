from __future__ import unicode_literals
from django.conf import settings

RA_TOPSEARCH_VIEW_CLASS = getattr(settings, 'RA_TOPSEARCH_VIEW_CLASS', 'ra.top_search.views.TopSearch')
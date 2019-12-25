from __future__ import unicode_literals

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.db.models import Q
from django.http import JsonResponse
from django.views.generic import FormView

from .forms import SearchForm
from ra.base.app_settings import RA_ADMIN_SITE_NAME

# todo  Revise Index
# todo: Revise the Models / DocTypes Dicts and make them look for the admin for correct reversing (change / view)

arabic_hindi_number_map = {1776: 48,  # 0
                           1777: 49,  # 1
                           1778: 50,  # 2
                           1779: 51,  # 3
                           1780: 52,  # 4
                           1781: 53,  # 5
                           1782: 54,  # 6
                           1783: 55,  # 7
                           1784: 56,  # 8
                           1785: 57}  # 9


class TopSearchViewBase(LoginRequiredMixin, FormView):
    form_class = SearchForm
    backend = 'database'

    def get_form_kwargs(self):
        """
        Returns the keyword arguments for instantiating the form.
        """
        kwargs = {
            'initial': self.get_initial(),
            'prefix': self.get_prefix(),
        }

        if self.request.method in ('GET',):
            kwargs.update({
                'data': self.request.GET,
                'files': self.request.FILES,
            })
        return kwargs

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        results = self.get_search_results(form)
        return JsonResponse({'data': results}, status=200)
        # return self.render_to_response(self.get_context_data(form=form))

    def get_search_results(self, form):
        results = []

        if form.is_valid():
            q = form.cleaned_data['q']
            q = q.translate(arabic_hindi_number_map)
            results = self.get_database_search_results(q)
        return results

    def get_database_search_results(self, q):
        from .models import TopSearchModel
        qs = Q(slug__icontains=q) | Q(title__icontains=q)
        qs = TopSearchModel.objects.filter(qs)
        return self.format_results_database(qs[:20])

    def format_results_database(self, qs):
        results = []
        get_url = self.get_link
        for suggestion in qs:
            results.append(
                {'id': suggestion.id,
                 'title': suggestion.title,
                 'slug': suggestion.slug,
                 'url': get_url(suggestion),
                 'origin': '-',
                 'origin_type': '-'
                 }
            )
        return results

    def get_link(self, result):
        from ra.base.registry import get_ra_model_by_name
        from django.urls import NoReverseMatch
        model_name = result.identifier
        model = get_ra_model_by_name(result.identifier)
        try:
            redirect_url = reverse(
                '%s:%s_%s_view' % (RA_ADMIN_SITE_NAME, model._meta.app_label, model._meta.model_name),
                args=(result.id,))
        except NoReverseMatch:
            redirect_url = reverse(
                '%s:%s_%s_change' % (RA_ADMIN_SITE_NAME, model._meta.app_label, model._meta.model_name),
                args=(result.id,))

        return redirect_url


class TopSearchView(TopSearchViewBase):
    pass

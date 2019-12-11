from django.apps import apps
from django.contrib.admin.sites import NotRegistered
from django.urls import NoReverseMatch

from .loading import get_baseinfo_model


class RaModelsRegistry(object):
    def __init__(self):
        super(RaModelsRegistry, self).__init__()
        self._registry = {}

    def populate(self):
        if self._registry:
            return

        models = apps.get_models()
        for m in models:
            self._registry[m._meta.model_name.lower()] = m

    def get(self, model_name):
        try:
            model = self._registry[model_name.lower()]
        except:
            raise NotRegistered('Model name %s not identified. Are you sure that the model exsits and its '
                                'app is added to INSTALLED_APPS ?' % model_name)

        return model


_models = None
ra_model_registry = RaModelsRegistry()


def get_ra_models():
    BaseInfo = get_baseinfo_model()
    # from . models import CostCenter
    global _models
    if not _models:
        model_list = apps.get_models()
        ra_model_list = [x for x in model_list if BaseInfo in x.__mro__]
        # ra_model_list = [x for x in model_list if BaseInfo in x.__mro__ or x is CostCenter]
        _models = ra_model_list
    return _models


def get_ra_model_by_name(model_name):
    ra_model_registry.populate()
    return ra_model_registry.get(model_name)


_doc_types = []
model_doc_type_map = {}
registry = ''

models_settings = {}
_doc_type_map = {}
model_doc_type_full_map = {}


def register_doc_type(*doc_types):
    for doc_type in doc_types:
        _doc_types.append(doc_type)

        _doc_type_map[doc_type['name']] = doc_type
        if 'plus_list' in doc_type:

            for plus_item in doc_type['plus_list']:
                if not plus_item in model_doc_type_full_map:
                    model_doc_type_full_map[plus_item] = []
                model_doc_type_full_map[plus_item].append(doc_type)

                if not plus_item in model_doc_type_map:
                    model_doc_type_map[plus_item] = {'plus_list': [], 'minus_list': []}
                model_doc_type_map[plus_item]['plus_list'].append(doc_type['name'])
        if 'minus_list' in doc_type:
            for plus_item in doc_type['minus_list']:
                if not plus_item in model_doc_type_map:
                    model_doc_type_map[plus_item] = {'plus_list': [], 'minus_list': []}
                model_doc_type_map[plus_item]['minus_list'].append(doc_type['name'])

                if not plus_item in model_doc_type_full_map:
                    model_doc_type_full_map[plus_item] = []
                model_doc_type_full_map[plus_item].append(doc_type)


def get_doc_type_settings():
    return _doc_type_map


def get_model_doc_type_map(model_name):
    return model_doc_type_map.get(model_name, {'plus_list': [], 'minus_list': []})


def get_model_settings():
    if not models_settings:
        _fill_models_settings()
    return models_settings


def _fill_models_settings():
    ra_models = list(get_ra_models())
    for model in ra_models:
        try:
            url = model.get_redirect_url_prefix()
        except NoReverseMatch:
            url = ''

        models_settings[model.__name__.lower()] = {'model': model, 'redirect_url_prefix': url}


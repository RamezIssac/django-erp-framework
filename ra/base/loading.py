"""
This module is responsible for the loading of the Base abstract classes as those classes are not
handleed by swapper
ref: https://github.com/wq/django-swappable-models/issues/3
"""

import swapper
from django.db.models.base import ModelBase
from django.core.exceptions import AppRegistryNotReady
from django.apps import apps as dj_apps
from django.utils.module_loading import import_string

from .app_settings import *

get_model = dj_apps.get_model


def get_baseinfo_model():
    return import_string(RA_BASEINFO_MODEL) or RA_BASEINFO_MODEL


get_baseinfo_model_lazy = lazy(get_baseinfo_model, ModelBase)


def get_basemovementinfo_model():
    model_path = RA_BASEMOVEMENTINFO_MODEL
    model = import_string(model_path)
    return model or model_path


def get_quanvaluemovementitem_model():
    return import_string(RA_QUANVALUEMOVEMENTITEM_MODEL) or RA_QUANVALUEMOVEMENTITEM_MODEL

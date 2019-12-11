from __future__ import unicode_literals

import logging

from django.apps import apps
from django.core.cache import cache
from django.db.models import Model
from django.utils.encoding import force_text

from ra.base.app_settings import RA_AUTOCOMPLETE_ALIASES

get_model = apps.get_model

logger = logging.getLogger(__name__)

#todo fix vaunerable to thunderheard


def get_cached_name(model_name, instance_id, default=None, model_class=None):

    if model_name == 'matrix_entities': return '-'  #fixme i'm a hack
    if model_class:
        model_name = model_class._meta.model_name
    return force_text(_get_cached_slug_title(model_name, instance_id, 'title', default, model_klass=model_class))


def get_cached_slug(model_name, instance_id, default=None, model_klass=None):
    if model_name == 'matrix_entities' or instance_id is None: return '-'  # fixme i'm a hack
    value = cache.get('%s_%s_slug' % (model_name, instance_id))
    if value is None:
        if default is None:
            update_slug_title_cache(model_name, instance_id)
            return get_cached_slug(model_name, instance_id, 'n/a')
        elif default == 'n/a':
            logger.error('Problem With ra_cache , Are we having enough CACHES[OPTIONS][MAX_ENTRIES] ?!')
            logger.error('model_name:%s \t instance_id: %s \t ' % (model_name, instance_id))
            return 'temporary not available'

        else:
            return default
    return value


def _get_cached_slug_title(model_name, instance_id, ikey, default=None, model_klass=None):
    value = cache.get('%s_%s_%s' % (model_name, instance_id, ikey))
    if value is None:
        if default is None:
            update_slug_title_cache(model_name, instance_id, model_klass=model_klass)
            if ikey == 'title':
                return get_cached_name(model_name, instance_id, 'n/a', model_class=model_klass)
            else:
                return get_cached_slug(model_name, instance_id, 'n/a', model_class=model_klass)
        elif default == 'n/a':

            logger.error('Problem With ra_cache , Are we having enough CACHES[OPTIONS][MAX_ENTRIES] ?!')
            logger.error('model_name:%s \t instance_id: %s \t  ikey:%s' % (model_name, instance_id, ikey))

            return 'temporary not available'

        else:
            return default
    return value


def update_slug_title_cache(model_name, instance_id, all=True, model_klass=None):
    from ra.base.registry import get_model_settings
    _model = None
    if model_klass is None:
        MODELS = get_model_settings()

        if model_name in MODELS:
            _model = MODELS[model_name]['model']
        elif model_name in RA_AUTOCOMPLETE_ALIASES:
            _model = get_model(*RA_AUTOCOMPLETE_ALIASES[model_name].split('.'))
    else:
        _model = model_klass


    logger.info('UPDATING CACHE FOR MODEL %s' % _model)
    if not Model in _model.__mro__:
        logging.error('Failed to get the model for %s' % model_name)

    if all:
        secondary_field = 'title'
        try:
            try:
                values = _model.objects.all_objects().values('id', 'slug', 'title')
            except:
                values = _model.objects.values('id', 'slug', 'title')
            if values:
                pass
        except Exception as e:  # todo , make it more smart to detect if model contain title
            values = _model.objects.values('id', 'slug', 'doc_date')
            secondary_field = 'doc_date'

        for m in values:
            cache.set('%s_%s_title' % (model_name, m['id']), m[secondary_field], 60 * 60)
            cache.set('%s_%s_slug' % (model_name, m['id']), m['slug'], 60 * 60)
    else:
        pass

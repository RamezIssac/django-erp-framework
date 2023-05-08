from django.apps import apps
from django.contrib.admin.sites import NotRegistered


# from .loading import get_baseinfo_model


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
            options = self._registry.keys()
            raise NotRegistered(
                f"Model name {model_name} not identified. options are {options}. \n Are you sure that the model exsits and its "
                "app is added to INSTALLED_APPS ?"
            )

        return model


_models = None
ra_model_registry = RaModelsRegistry()


def get_ra_model_by_name(model_name):
    ra_model_registry.populate()
    return ra_model_registry.get(model_name)


_doc_types = []
model_doc_type_map = {}

model_doc_type_full_map = {}


def register_doc_type(*doc_types):
    for doc_type in doc_types:
        _doc_types.append(doc_type)

        if "plus_list" in doc_type:
            for model_name in doc_type["plus_list"]:
                # if not model_name in model_doc_type_full_map:
                #     model_doc_type_full_map[model_name] = []
                # model_doc_type_full_map[model_name].append(doc_type)
                if model_name not in model_doc_type_map:
                    model_doc_type_map[model_name] = {"plus_list": [], "minus_list": []}
                model_doc_type_map[model_name]["plus_list"].append(doc_type["name"])

        if "minus_list" in doc_type:
            for model_name in doc_type["minus_list"]:
                model_doc_type_map[model_name].setdefault(
                    {"plus_list": [], "minus_list": []}
                )
                model_doc_type_map[model_name]["minus_list"].append(doc_type["name"])

                # if not model_name in model_doc_type_full_map:
                #     model_doc_type_full_map[model_name] = []
                # model_doc_type_full_map[model_name].append(doc_type)


def get_model_doc_type_map(model_name):
    return model_doc_type_map.get(model_name, {"plus_list": [], "minus_list": []})

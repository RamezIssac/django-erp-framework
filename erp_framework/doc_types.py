from dataclasses import dataclass


@dataclass
class DocType:
    name: str
    plus_side: list = None
    minus_side: list = None
    verbose_name: str = None

    @classmethod
    def to_dict(self):
        return {
            "plus_list": self.plus_side or [],
            "minus_list": self.minus_side or [],
            "name": self.name,
            "verbose_name": self.verbose_name or self.name
        }


class ChildTracker(type):
    """A metaclass that tracks the child classes of a class."""

    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        new_class._child_classes = set()
        return new_class

    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        for base in bases:
            if isinstance(base, ChildTracker):
                cls._child_classes.update(base._child_classes)

    def add_child(self, child):
        """Adds a child class to the class."""
        self._child_classes.add(child)

    def get_child_classes(self):
        """Returns a set of the child classes of the class."""
        return self._child_classes


from collections import OrderedDict

from django.contrib.admin.sites import AlreadyRegistered, NotRegistered
from django.core.exceptions import ImproperlyConfigured


class DocTypeRegistry(object):
    def __init__(self):
        super().__init__()
        self._registry = OrderedDict()
        self.model_doc_type_map = {}

        self._slugs_registry = []
        self._store = {}
        self._base_models = []

    def register(self, doc_type):
        """
        Register report class
        :param doc_type:
        :return:
        """

        if type(doc_type) is not dict:
            try:
                doc_type = doc_type.to_dict()
            except AttributeError:
                raise ImproperlyConfigured(f"{doc_type} is not a dict or DocType")

        doc_type_dict = doc_type if type(doc_type) is dict else doc_type.to_dict()

        for key in ["plus_list", "minus_list"]:
            if key in doc_type_dict:
                for model_name in doc_type_dict[key]:
                    # if not model_name in model_doc_type_full_map:
                    #     model_doc_type_full_map[model_name] = []
                    # model_doc_type_full_map[model_name].append(doc_type)
                    if model_name not in self.model_doc_type_map:
                        self.model_doc_type_map[model_name] = {"plus_list": [], "minus_list": []}
                    # add the doc_type name to the model
                    self.model_doc_type_map[model_name][key].append(doc_type_dict["name"])

    def get(self, model_name):
        return self.model_doc_type_map.get(model_name, {"plus_list": [], "minus_list": []})

    def set(self, model_name, plus_list=None, minus_list=None):
        original_plus_list, original_minus_list = self.get(model_name)
        if plus_list:
            original_plus_list = plus_list
        if minus_list:
            original_minus_list = minus_list
        self.model_doc_type_map[model_name] = {"plus_list": original_plus_list, "minus_list": original_minus_list}

    def append(self, model_name, plus_list=None, minus_list=None):
        original_plus_list, original_minus_list = self.get(model_name)
        if plus_list:
            original_plus_list += plus_list
        if minus_list:
            original_minus_list += minus_list
        self.model_doc_type_map[model_name] = {"plus_list": original_plus_list, "minus_list": original_minus_list}

    def remove(self, model_name, plus_list=None, minus_list=None):
        original_plus_list, original_minus_list = self.get(model_name)
        if plus_list:
            for item in plus_list:
                original_plus_list.remove(item)
        if minus_list:
            for item in minus_list:
                original_minus_list.remove(item)
        self.model_doc_type_map[model_name] = {"plus_list": original_plus_list, "minus_list": original_minus_list}


doc_type_registry = DocTypeRegistry()

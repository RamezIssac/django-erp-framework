"""
Document type effects: how each transaction class moves the entities it points to.

A transaction class declares ``doc_type_effects = {"<fk field name>": PLUS | MINUS | None}``.
Subclasses inherit the declaration and may add, override or neutralise (``None``) entries.
"""

from collections import namedtuple
from collections.abc import Mapping
from enum import IntEnum

from django.apps import apps
from django.core import checks
from django.core.exceptions import FieldDoesNotExist


class Effect(IntEnum):
    PLUS = 1
    MINUS = -1


PLUS = Effect.PLUS
MINUS = Effect.MINUS

DocTypes = namedtuple("DocTypes", ["plus", "minus"])


def get_effects(model):
    """Return the effects of ``model`` merged along its MRO, the most derived class winning."""
    effects = {}
    for klass in reversed(model.__mro__):
        effects.update(klass.__dict__.get("doc_type_effects") or {})
    return effects


def transaction_models(include_proxies=True):
    from erp_framework.base.models import TransactionModel

    return [
        model
        for model in apps.get_models()
        if issubclass(model, TransactionModel)
        and (include_proxies or not model._meta.proxy)
    ]


def entity_foreign_key(model, field_name, entity):
    """Return the FK ``field_name`` of ``model`` when it points to ``entity``, else None."""
    try:
        field = model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return None
    if not field.many_to_one or field.related_model is None:
        return None
    if field.related_model._meta.concrete_model is not entity._meta.concrete_model:
        return None
    return field


def for_entity(entity, field_name=None):
    """
    Return the ``DocTypes(plus, minus)`` lists of every transaction type that moves ``entity``
    through its FK ``field_name`` (default: the entity's model name).
    """
    field_name = field_name or entity._meta.model_name
    plus, minus = set(), set()
    for model in transaction_models():
        if entity_foreign_key(model, field_name, entity) is None:
            continue
        effect = get_effects(model).get(field_name)
        if effect == PLUS:
            plus.add(model.get_doc_type())
        elif effect == MINUS:
            minus.add(model.get_doc_type())
    return DocTypes(sorted(plus), sorted(minus))


def _is_entity_target(field):
    from erp_framework.base.models import EntityModel, TransactionModel

    target = field.related_model
    return (
        isinstance(target, type)
        and issubclass(target, EntityModel)
        and not issubclass(target, TransactionModel)
    )


def _check_declaration(model, effects):
    errors = []
    for field_name, effect in effects.items():
        try:
            field = model._meta.get_field(field_name)
        except FieldDoesNotExist:
            field = None
        if field is None or not field.many_to_one:
            errors.append(
                checks.Error(
                    f"doc_type_effects names '{field_name}', which is not a foreign key "
                    f"of {model._meta.label}.",
                    hint="Use the name of a ForeignKey field of the model.",
                    obj=model,
                    id="erp_framework.E004",
                )
            )
        if effect is not None and (isinstance(effect, bool) or effect not in (1, -1)):
            errors.append(
                checks.Error(
                    f"doc_type_effects['{field_name}'] of {model._meta.label} is {effect!r}.",
                    hint="Use PLUS, MINUS or None from erp_framework.doc_types.",
                    obj=model,
                    id="erp_framework.E005",
                )
            )
    return errors


def check_doc_type_effects(models):
    """Run the doc type checks over ``models`` (the transaction models of the project)."""
    errors = []
    signs = {}
    for model in models:
        if model._meta.proxy and "doc_type_effects" not in model.__dict__:
            continue
        declared = [k.__dict__.get("doc_type_effects") for k in model.__mro__]
        if any(d is not None and not isinstance(d, Mapping) for d in declared):
            errors.append(
                checks.Error(
                    f"doc_type_effects of {model._meta.label} is not a dict.",
                    obj=model,
                    id="erp_framework.E004",
                )
            )
            continue
        effects = get_effects(model)
        errors.extend(_check_declaration(model, effects))
        for field in model._meta.get_fields():
            if not field.many_to_one or not field.concrete:
                continue
            if not _is_entity_target(field):
                continue
            if field.name not in effects:
                errors.append(
                    checks.Warning(
                        f"{model._meta.label} has a foreign key '{field.name}' to "
                        f"{field.related_model._meta.label} and no doc_type_effects entry for it.",
                        hint=f"Declare doc_type_effects = {{'{field.name}': PLUS}} (or MINUS, "
                        "or None for no effect) on the class or one of its bases.",
                        obj=model,
                        id="erp_framework.W001",
                    )
                )
            elif effects[field.name] in (1, -1):
                key = (
                    field.related_model._meta.concrete_model,
                    field.name,
                    model.get_doc_type(),
                )
                signs.setdefault(key, {})[model] = effects[field.name]
    for (entity, field_name, doc_type), by_model in signs.items():
        if len(set(by_model.values())) > 1:
            labels = ", ".join(sorted(m._meta.label for m in by_model))
            errors.append(
                checks.Error(
                    f"Document type '{doc_type}' is both PLUS and MINUS for "
                    f"{entity._meta.label} through '{field_name}' ({labels}).",
                    hint="Give the classes distinct get_doc_type() values or the same effect.",
                    obj=doc_type,
                    id="erp_framework.E006",
                )
            )
    return errors

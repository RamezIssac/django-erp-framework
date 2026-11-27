"""
Movements views: one database view per entity, a UNION ALL over every transaction table with a
foreign key to it. The SQL is generated from model metadata and rebuilt on each ``migrate``.
"""

import sys
from dataclasses import dataclass

from django.apps import apps
from django.core.checks import Error
from django.core.exceptions import FieldDoesNotExist
from django.db import DEFAULT_DB_ALIAS, connections, models, router
from django.utils.translation import gettext_lazy as _

from .doc_types import entity_foreign_key, transaction_models

MOVEMENTS_PREFIX = "erp_movements_"
LEGACY_PREFIX = "erp_ledger_"  # earlier name of these views, dropped by every migrate
SUPPORTED_VENDORS = ("postgresql", "sqlite")
NUMERIC_FIELDS = (models.IntegerField, models.DecimalField, models.FloatField)


class MovementsModel(models.Model):
    """Columns shared by every movements model; ``entity_movements()`` adds the entity foreign key."""

    id = models.TextField(primary_key=True)
    date = models.DateTimeField(_("Date"))
    slug = models.SlugField(_("Slug"), max_length=50)
    type = models.CharField(_("Type"), max_length=30)
    value = models.DecimalField(_("Value"), max_digits=19, decimal_places=2)
    content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="+",
    )
    object_id = models.TextField()

    class Meta:
        abstract = True


@dataclass(frozen=True)
class MovementsSpec:
    include_numeric: bool
    columns: dict  # {column: {source model name or label: field name}}
    exclude: tuple
    sources: tuple | None


def entity_movements(entity, name=None, include_numeric=False, columns=None, exclude=None, sources=None):
    """
    Return an unmanaged model ``name`` (default ``<Entity>Movements``) over the view
    ``erp_movements_<app>_<name>`` of the app that calls it. Assign it in a models module.

    ``include_numeric`` adds every numeric field of the sources except ``exclude``. ``columns`` adds
    named fields, as a list or as ``{column: {source: field}}``. ``sources`` restricts the tables.
    """
    module = sys._getframe(1).f_globals.get("__name__", "__main__")
    config = apps.get_containing_app_config(module)
    name = name or f"{entity.__name__}Movements"
    field_name = entity._meta.model_name
    if isinstance(columns, dict):
        columns = {column: dict(fields) for column, fields in columns.items()}
    else:
        columns = dict.fromkeys(columns or (), {})
    reserved = _reserved_names(field_name)
    if clashes := sorted(reserved & columns.keys()):
        raise ValueError(f"columns {clashes} are base columns of the movements view.")
    app_label = config.label if config else entity._meta.app_label
    meta = {
        "managed": False,
        "db_table": f"{MOVEMENTS_PREFIX}{app_label}_{name.lower()}",
        "default_permissions": ("view",),
    }
    attrs = {
        "__module__": module,
        "Meta": type("Meta", (), meta),
        "movements_entity": entity,
        "movements_field": field_name,
        "movements_spec": MovementsSpec(
            include_numeric,
            columns,
            tuple(exclude or ()),
            None if sources is None else tuple(sources),
        ),
        field_name: models.ForeignKey(
            entity,
            on_delete=models.DO_NOTHING,
            db_constraint=False,
            related_name="+",
            verbose_name=entity._meta.verbose_name,
        ),
    }
    return type(name, (MovementsModel,), attrs)


def _reserved_names(field_name):
    base = {f.name for f in MovementsModel._meta.fields} | {"content_type_id"}
    return base | {field_name, f"{field_name}_id"}


def movements_models():
    return [model for model in apps.get_models() if issubclass(model, MovementsModel)]


def movement_sources(movements_model):
    """
    Return the source models, one per table: the declared ``sources``, or else every transaction
    table holding the entity foreign key, sorted by label.
    """
    declared = movements_model.movements_spec.sources
    if declared is not None:
        return [model._meta.concrete_model for model in declared]
    owners = {}
    models = transaction_models(include_proxies=False)
    for model in models:
        fk = entity_foreign_key(model, movements_model.movements_field, movements_model.movements_entity)
        owner = fk and fk.model._meta.concrete_model
        if owner in models and owner._meta.managed:
            owners[owner._meta.label_lower] = owner
    return [owners[label] for label in sorted(owners)]


def _field(model, name):
    try:
        return model._meta.get_field(name)
    except FieldDoesNotExist:
        return None


def _is_numeric(field):
    return isinstance(field, NUMERIC_FIELDS) and not field.primary_key


def _field_type(field):
    return field.get_internal_type(), getattr(field, "decimal_places", None)


def movement_columns(movements_model):
    """
    Return ``{column: {source: field or None}}``. The first call adds each column to the model as a
    nullable copy of its first numeric source field.
    """
    if "_movement_columns" in movements_model.__dict__:
        return movements_model._movement_columns
    spec = movements_model.movements_spec
    sources = movement_sources(movements_model)
    names = list(spec.columns)
    if spec.include_numeric:
        skipped = _reserved_names(movements_model.movements_field) | set(spec.exclude)
        for source in sources:
            for field in source._meta.concrete_fields:
                if _is_numeric(field) and field.name not in skipped and field.name not in names:
                    names.append(field.name)
    resolved = {}
    for column in names:
        mapping = spec.columns.get(column, {})
        resolved[column] = {
            source: _field(source, mapping.get(source.__name__) or mapping.get(source._meta.label) or column)
            for source in sources
        }
        numeric = [f for f in resolved[column].values() if _is_numeric(f)]
        kwargs = {"max_digits": 19, "decimal_places": 2}
        field_class = models.DecimalField
        if numeric:
            field_class = type(numeric[0])
            kwargs = {k: getattr(numeric[0], k) for k in ("max_digits", "decimal_places") if hasattr(numeric[0], k)}
        field_class(column.replace("_", " "), null=True, **kwargs).contribute_to_class(movements_model, column)
    movements_model._meta._expire_cache()
    movements_model._movement_columns = resolved
    return resolved


def _quote(name):
    return '"%s"' % name.replace('"', '""')


def _sql_str(value):
    return "'%s'" % value.replace("'", "''")


def _source_select(movements_model, owner, index, connection):
    """Return the SELECT of one source table and the ``{table: {columns}}`` it reads."""
    alias = f"s{index}"
    meta = owner._meta
    joins = {}
    required = {meta.db_table: {meta.pk.column}}

    def column(field_name):
        try:
            field = meta.get_field(field_name)
        except FieldDoesNotExist:
            return None
        holder = field.model._meta.concrete_model
        holder_alias = alias
        if holder is not owner:
            holder_alias = joins.setdefault(holder, f"{alias}p{len(joins) + 1}")
            required.setdefault(holder._meta.db_table, {holder._meta.pk.column})
        required.setdefault(holder._meta.db_table, set()).add(field.column)
        return f"{holder_alias}.{_quote(field.column)}"

    pk = f"{alias}.{_quote(meta.pk.column)}"
    fk = column(movements_model.movements_field)
    ctype = column("polymorphic_ctype") or (
        f"(SELECT {_quote('id')} FROM {_quote('django_content_type')} "
        f"WHERE {_quote('app_label')} = {_sql_str(meta.app_label)} "
        f"AND {_quote('model')} = {_sql_str(meta.model_name)})"
    )
    values = {
        "id": f"{_sql_str(meta.label_lower + '-')} || CAST({pk} AS TEXT)",
        "date": column("date"),
        "slug": column("slug"),
        "type": column("type"),
        "value": column("value"),
        movements_model.movements_field: fk,
        "content_type": ctype,
        "object_id": f"CAST({pk} AS TEXT)",
    }
    for name, fields in movement_columns(movements_model).items():
        field = fields.get(owner)
        if _is_numeric(field):
            values[name] = column(field.name)
        else:
            db_type = movements_model._meta.get_field(name).cast_db_type(connection)
            values[name] = f"CAST(NULL AS {db_type})"
    projection = ",\n       ".join(
        f"{values[field.name]} AS {_quote(field.column)}"
        for field in movements_model._meta.concrete_fields
    )
    sql = f"SELECT {projection}\nFROM {_quote(meta.db_table)} {alias}"
    for holder, holder_alias in joins.items():
        sql += (
            f"\nJOIN {_quote(holder._meta.db_table)} {holder_alias} "
            f"ON {holder_alias}.{_quote(holder._meta.pk.column)} = {pk}"
        )
    return f"{sql}\nWHERE {fk} IS NOT NULL", required


def _empty_select(movements_model, connection):
    columns = []
    for field in movements_model._meta.concrete_fields:
        expression = "NULL"
        if connection.vendor == "postgresql":
            expression = f"CAST(NULL AS {field.cast_db_type(connection)})"
        columns.append(f"{expression} AS {_quote(field.column)}")
    return "SELECT " + ",\n       ".join(columns) + "\nWHERE 1 = 0"


def build_movements_sql(movements_model, connection, sources=None):
    """Return the CREATE VIEW statement for ``connection`` over ``sources`` (default: all)."""
    vendor = connection.vendor
    if vendor not in SUPPORTED_VENDORS:
        raise NotImplementedError(
            f"Movements views support {', '.join(SUPPORTED_VENDORS)}, not {vendor}."
        )
    movement_columns(movements_model)
    if sources is None:
        sources = movement_sources(movements_model)
    selects = [
        _source_select(movements_model, owner, i, connection)[0]
        for i, owner in enumerate(sources)
    ]
    body = "\nUNION ALL\n".join(selects or [_empty_select(movements_model, connection)])
    return f"CREATE VIEW {_quote(movements_model._meta.db_table)} AS\n{body}"


def _views_and_tables(connection):
    with connection.cursor() as cursor:
        table_list = connection.introspection.get_table_list(cursor)
    views = {t.name for t in table_list if t.type == "v"}
    return views, {t.name for t in table_list if t.type == "t"}


def present_sources(movements_model, connection, tables=None):
    """Return ``(present, missing)`` source models, by the tables and columns in the database."""
    if tables is None:
        tables = _views_and_tables(connection)[1]
    described = {}
    present, missing = [], []
    with connection.cursor() as cursor:
        for owner in movement_sources(movements_model):
            required = _source_select(movements_model, owner, 0, connection)[1]
            for table in required.keys() & tables:
                if table not in described:
                    description = connection.introspection.get_table_description(
                        cursor, table
                    )
                    described[table] = {column.name for column in description}
            ok = all(
                table in described and columns <= described[table]
                for table, columns in required.items()
            )
            (present if ok else missing).append(owner)
    return present, missing


def check_movements(checked_models):
    """System checks E007 to E010 of the movements models' sources and columns."""
    errors = []
    for model in checked_models:
        label = model._meta.label
        sources = movement_sources(model)

        def error(msg, id):
            errors.append(Error(msg, obj=model, id=f"erp_framework.{id}"))

        for source in sources:
            fk = entity_foreign_key(source, model.movements_field, model.movements_entity)
            if fk is None:
                error(f"Source {source._meta.label} of {label} has no foreign key '{model.movements_field}' "
                      f"to {model.movements_entity._meta.label}.", "E010")
            for other in sources:
                if other is not source and issubclass(other, source):
                    error(f"Sources {source._meta.label} and {other._meta.label} of {label} share rows: "
                          "list one of them.", "E010")
        names = {s.__name__ for s in sources} | {s._meta.label for s in sources}
        for column, mapping in model.movements_spec.columns.items():
            for key in sorted(mapping.keys() - names):
                error(f"Column '{column}' of {label} maps '{key}', which is not a source.", "E009")
        for column, fields in movement_columns(model).items():
            other = [s._meta.label for s, f in fields.items() if f and not _is_numeric(f)]
            numeric = [(s, f) for s, f in fields.items() if _is_numeric(f)]
            if other:
                error(f"Column '{column}' of {label} is not numeric on {', '.join(other)}.", "E007")
            elif not numeric:
                error(f"Column '{column}' of {label} is not a field of any source.", "E007")
            mismatched = [(s, f) for s, f in numeric if _field_type(f) != _field_type(numeric[0][1])]
            if mismatched:
                (first, a), (second, b) = numeric[0], mismatched[0]
                error(f"Column '{column}' of {label} is {_describe(a)} on {first._meta.label} "
                      f"and {_describe(b)} on {second._meta.label}.", "E008")
    return errors


def _describe(field):
    kind, places = _field_type(field)
    return kind if places is None else f"{kind}({places} places)"


def drop_movement_views(using=DEFAULT_DB_ALIAS):
    """Drop the views of the current movements models and every view named with either prefix."""
    connection = connections[using]
    views, _tables = _views_and_tables(connection)
    names = {model._meta.db_table for model in movements_models()}
    prefixes = (MOVEMENTS_PREFIX, LEGACY_PREFIX)
    doomed = sorted(v for v in views if v in names or v.startswith(prefixes))
    with connection.cursor() as cursor:
        for name in doomed:
            cursor.execute(f"DROP VIEW {_quote(name)}")
    return doomed


def create_movement_views(using=DEFAULT_DB_ALIAS, verbosity=1, stdout=None):
    """
    (Re)create the view of every movements model whose entity table exists in ``using``.
    Return ``[(view name, present sources, missing sources)]``.
    """
    stdout = stdout or sys.stdout
    connection = connections[using]
    tables = _views_and_tables(connection)[1]
    created = []
    for movements_model in movements_models():
        meta = movements_model._meta
        if not router.allow_migrate(using, meta.app_label, model_name=meta.model_name):
            continue
        if movements_model.movements_entity._meta.db_table not in tables:
            continue
        present, missing = present_sources(movements_model, connection, tables)
        with connection.cursor() as cursor:
            cursor.execute(f"DROP VIEW IF EXISTS {_quote(meta.db_table)}")
            cursor.execute(build_movements_sql(movements_model, connection, present))
        created.append((meta.db_table, present, missing))
        if verbosity >= 2:
            stdout.write(
                f"  Movements view {meta.db_table}: {len(present)} source table(s)\n"
            )
        if missing and verbosity >= 1:
            labels = ", ".join(model._meta.label for model in missing)
            stdout.write(
                f"  Movements view {meta.db_table} skips {labels}: table or column not migrated yet\n"
            )
    return created


def _migrated_app_configs():
    return [
        config for config in apps.get_app_configs() if config.models_module is not None
    ]


def drop_movement_views_before_migrate(sender, using, plan=None, **kwargs):
    """``pre_migrate`` receiver: runs once per ``migrate`` command, on its first signal."""
    if plan is not None and sender is _migrated_app_configs()[0]:
        drop_movement_views(using)


def create_movement_views_after_migrate(sender, using, plan=None, verbosity=1, **kwargs):
    """``post_migrate`` receiver: runs once per ``migrate`` command, on its last signal."""
    if plan is not None and sender is _migrated_app_configs()[-1]:
        create_movement_views(using, verbosity=verbosity, stdout=kwargs.get("stdout"))

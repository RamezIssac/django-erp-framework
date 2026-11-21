"""
Ledger views: one database view per entity, a UNION ALL over every transaction table with a
foreign key to it. The SQL is generated from model metadata and rebuilt on each ``migrate``.
"""

import sys

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import DEFAULT_DB_ALIAS, connections, models, router
from django.utils.translation import gettext_lazy as _

from .doc_types import entity_foreign_key, transaction_models

LEDGER_PREFIX = "erp_ledger_"
SUPPORTED_VENDORS = ("postgresql", "sqlite")

# Postgres types for the typed NULL row of a ledger view with no source table.
_POSTGRES_TYPES = {
    "AutoField": "integer",
    "BigAutoField": "bigint",
    "SmallAutoField": "smallint",
    "IntegerField": "integer",
    "BigIntegerField": "bigint",
    "SmallIntegerField": "smallint",
    "PositiveIntegerField": "integer",
    "PositiveBigIntegerField": "bigint",
    "UUIDField": "uuid",
    "TextField": "text",
    "DateTimeField": "timestamp with time zone",
    "CharField": "varchar(%(max_length)s)",
    "SlugField": "varchar(%(max_length)s)",
    "DecimalField": "numeric(%(max_digits)s, %(decimal_places)s)",
}


class LedgerModel(models.Model):
    """Columns shared by every ledger; ``ledger_model()`` adds the entity foreign key."""

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

    ledger_entity = None
    ledger_field = None

    class Meta:
        abstract = True


def ledger_model(entity, field_name=None, *, name=None, db_table=None, app_label=None):
    """
    Return an unmanaged model over the ledger view of ``entity`` with the FK ``field_name``
    (default: the entity's model name). Assign it in a models module.
    """
    field_name = field_name or entity._meta.model_name
    meta = {
        "managed": False,
        "db_table": db_table
        or f"{LEDGER_PREFIX}{entity._meta.app_label}_{entity._meta.model_name}",
        "default_permissions": ("view",),
    }
    if app_label:
        meta["app_label"] = app_label
    attrs = {
        "__module__": sys._getframe(1).f_globals.get("__name__", "__main__"),
        "Meta": type("Meta", (), meta),
        "ledger_entity": entity,
        "ledger_field": field_name,
        field_name: models.ForeignKey(
            entity,
            on_delete=models.DO_NOTHING,
            db_constraint=False,
            related_name="+",
            verbose_name=entity._meta.verbose_name,
        ),
    }
    return type(name or f"{entity.__name__}Ledger", (LedgerModel,), attrs)


def ledger_models():
    return [model for model in apps.get_models() if issubclass(model, LedgerModel)]


def ledger_sources(ledger):
    """Return the models whose tables hold the ledger's foreign key, one per table, sorted by label."""
    owners = {}
    models = transaction_models(include_proxies=False)
    for model in models:
        fk = entity_foreign_key(model, ledger.ledger_field, ledger.ledger_entity)
        owner = fk and fk.model._meta.concrete_model
        if owner in models and owner._meta.managed:
            owners[owner._meta.label_lower] = owner
    return [owners[label] for label in sorted(owners)]


def _quote(name):
    return '"%s"' % name.replace('"', '""')


def _sql_str(value):
    return "'%s'" % value.replace("'", "''")


def _source_select(ledger, owner, index):
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
    fk = column(ledger.ledger_field)
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
        ledger.ledger_field: fk,
        "content_type": ctype,
        "object_id": f"CAST({pk} AS TEXT)",
    }
    projection = ",\n       ".join(
        f"{values[field.name]} AS {_quote(field.column)}"
        for field in ledger._meta.concrete_fields
    )
    sql = f"SELECT {projection}\nFROM {_quote(meta.db_table)} {alias}"
    for holder, holder_alias in joins.items():
        sql += (
            f"\nJOIN {_quote(holder._meta.db_table)} {holder_alias} "
            f"ON {holder_alias}.{_quote(holder._meta.pk.column)} = {pk}"
        )
    return f"{sql}\nWHERE {fk} IS NOT NULL", required


def _empty_select(ledger, vendor):
    columns = []
    for field in ledger._meta.concrete_fields:
        expression = "NULL"
        if vendor == "postgresql":
            target = field.target_field if field.is_relation else field
            sql_type = _POSTGRES_TYPES.get(target.get_internal_type(), "text")
            expression = f"CAST(NULL AS {sql_type % target.__dict__})"
        columns.append(f"{expression} AS {_quote(field.column)}")
    return "SELECT " + ",\n       ".join(columns) + "\nWHERE 1 = 0"


def build_ledger_sql(ledger, vendor, sources=None):
    """Return the CREATE VIEW statement of ``ledger`` for ``vendor`` over ``sources`` (default: all)."""
    if vendor not in SUPPORTED_VENDORS:
        raise NotImplementedError(
            f"Ledger views support {', '.join(SUPPORTED_VENDORS)}, not {vendor}."
        )
    if sources is None:
        sources = ledger_sources(ledger)
    selects = [_source_select(ledger, owner, i)[0] for i, owner in enumerate(sources)]
    body = "\nUNION ALL\n".join(selects or [_empty_select(ledger, vendor)])
    return f"CREATE VIEW {_quote(ledger._meta.db_table)} AS\n{body}"


def _views_and_tables(connection):
    with connection.cursor() as cursor:
        table_list = connection.introspection.get_table_list(cursor)
    views = {t.name for t in table_list if t.type == "v"}
    return views, {t.name for t in table_list if t.type == "t"}


def present_sources(ledger, connection, tables=None):
    """Return ``(present, missing)`` source models, by the tables and columns in the database."""
    if tables is None:
        tables = _views_and_tables(connection)[1]
    described = {}
    present, missing = [], []
    with connection.cursor() as cursor:
        for owner in ledger_sources(ledger):
            required = _source_select(ledger, owner, 0)[1]
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


def drop_ledger_views(using=DEFAULT_DB_ALIAS):
    """Drop every ledger view: those of the current ledger models and any ``erp_ledger_*`` view."""
    connection = connections[using]
    views, _tables = _views_and_tables(connection)
    names = {ledger._meta.db_table for ledger in ledger_models()}
    doomed = sorted(v for v in views if v in names or v.startswith(LEDGER_PREFIX))
    with connection.cursor() as cursor:
        for name in doomed:
            cursor.execute(f"DROP VIEW {_quote(name)}")
    return doomed


def create_ledger_views(using=DEFAULT_DB_ALIAS, verbosity=1, stdout=None):
    """
    (Re)create the view of every ledger model whose entity table exists in ``using``.
    Return ``[(view name, present sources, missing sources)]``.
    """
    stdout = stdout or sys.stdout
    connection = connections[using]
    ledgers = ledger_models()
    if not ledgers:
        return []
    views, tables = _views_and_tables(connection)
    created = []
    for ledger in ledgers:
        meta = ledger._meta
        if not router.allow_migrate(using, meta.app_label, model_name=meta.model_name):
            continue
        if ledger.ledger_entity._meta.db_table not in tables:
            continue
        present, missing = present_sources(ledger, connection, tables)
        with connection.cursor() as cursor:
            if meta.db_table in views:
                cursor.execute(f"DROP VIEW {_quote(meta.db_table)}")
            cursor.execute(build_ledger_sql(ledger, connection.vendor, present))
        created.append((meta.db_table, present, missing))
        if verbosity >= 2:
            stdout.write(
                f"  Ledger view {meta.db_table}: {len(present)} source table(s)\n"
            )
        if missing and verbosity >= 1:
            labels = ", ".join(model._meta.label for model in missing)
            stdout.write(
                f"  Ledger view {meta.db_table} skips {labels}: table or column not migrated yet\n"
            )
    return created


def _migrated_app_configs():
    return [
        config for config in apps.get_app_configs() if config.models_module is not None
    ]


def drop_ledger_views_before_migrate(sender, using, plan=None, **kwargs):
    """``pre_migrate`` receiver: runs once per ``migrate`` command, on its first signal."""
    if plan is not None and sender is _migrated_app_configs()[0]:
        drop_ledger_views(using)


def create_ledger_views_after_migrate(sender, using, plan=None, verbosity=1, **kwargs):
    """``post_migrate`` receiver: runs once per ``migrate`` command, on its last signal."""
    if plan is not None and sender is _migrated_app_configs()[-1]:
        create_ledger_views(using, verbosity=verbosity, stdout=kwargs.get("stdout"))

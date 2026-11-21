"""
Registered reports and ad-hoc dynamic reports as read-only MCP tools.

Mix :class:`ReportToolsMixin` into a django-admin-api-mcp ``AdminMcpSite`` (``ERPMcpSite`` already
does)::

    class MyMcpSite(ReportToolsMixin, AdminMcpSite):
        report_max_rows = 100

The tools are ``list_reports``, ``describe_report``, ``run_report``, ``list_dynamic_report_models``
and ``run_dynamic_report``. The server instructions start with a catalog of the reports the user may
run, sized to fit ``instructions_max_chars``. Reports run through django-slick-reporting's
headless runner and come back as compact rows plus server-side totals. This module requires django-admin-api-mcp and
django-slick-reporting's headless runner, compact output and dynamic report; erp_framework itself does not.
"""

import copy

from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import (
    NON_FIELD_ERRORS,
    FieldDoesNotExist,
    ImproperlyConfigured,
    PermissionDenied,
    ValidationError,
)
from django.utils.translation import gettext

from admin_api import scopes
from admin_api.changelist import get_columns
from admin_api.detail import detail_fields
from admin_api.errors import ApiError, NotFound, PermissionDeniedError
from admin_api.jsonschema import form_object_schema
from admin_api.mcp.resolve import is_excluded
from admin_api.mcp.sites import DEFAULT_INSTRUCTIONS
from admin_api.mcp.tools import ToolSpec, obj
from slick_reporting.dynamic_report import (
    DYNAMIC_REPORT_SPEC_SCHEMA,
    FILTER_LOOKUPS,
    describe_dynamic_report_models,
    run_dynamic_report,
)
from slick_reporting.fields import ComputationField, FirstBalanceField
from slick_reporting.generator import ReportGenerator
from slick_reporting.helpers import compact_response
from slick_reporting.registry import field_registry
from slick_reporting.views import SlickReportingListViewMixin

from erp_framework.base import app_settings
from erp_framework.reporting.registry import report_registry

REPORT_TOOL_NAMES = frozenset(
    {"list_reports", "describe_report", "run_report", "list_dynamic_report_models", "run_dynamic_report"}
)

REPORT_INSTRUCTIONS = """
7. Reports: run one from the report catalog above with run_report (call list_reports when there is \
none, or to compare columns). Pass the IDs resolve_entities returns as a list, e.g. {'client_id': [5]}. \
Name a report by its 'title', a column and a record by its label.
Note: run a catalog report directly for a kind of record ('sales by client'), not resolve_entities or \
describe_model first, because the report already groups by it.
Note: answer totals and balances with a report, not list_objects rows you add up, because a hand sum \
hides what the report leaves out.
8. When no report answers, use list_dynamic_report_models and run_dynamic_report."""

# Catalog detail levels, richest first: get_instructions uses the first that fits instructions_max_chars.
CATALOG_HEADERS = {
    "questions": "Report catalog (code: question; params; balance = includes all before start_date):",
    "params": "Report catalog (code; params; list_reports has each question and its columns):",
    "codes": "Report catalog (codes; list_reports has each question, params and columns):",
}

READ_ONLY = {"readOnlyHint": True, "openWorldHint": False}
SPEC_SCHEMA = {k: v for k, v in DYNAMIC_REPORT_SPEC_SCHEMA.items() if k != "$schema"}

REPORT_ARG = {
    "type": "string",
    "description": "Report code exactly as listed in the report catalog or by list_reports "
    "(e.g. 'client.balances'). "
    "Tell the user the report's title, not its code.",
}


class InvalidParams(ApiError):
    status = 400
    code = "invalid_params"


class ReportToolsMixin:
    """Adds the report tools to an ``AdminMcpSite`` subclass.

    A report is listed and runnable when ``is_report_exposed`` allows it (default: its base model's
    admin is exposed through MCP), ``report_access_function(request, "view", report)`` passes, and the
    token scopes allow ``view`` on the report's base model.
    """

    report_max_rows = 200
    report_max_rows_cap = 1000
    report_catalog_max = 40
    # Claude Code reads the first 4,096 characters; lower it by what a subclass appends after the mixin.
    instructions_max_chars = 4096
    instructions = DEFAULT_INSTRUCTIONS + REPORT_INSTRUCTIONS

    # --- policy hooks (override in a subclass) -------------------------------------------------
    def is_report_exposed(self, report_class) -> bool:
        """Default: the report's base model is exposed (a report without a base model is kept)."""
        base_model = getattr(report_class, "base_model", None)
        return base_model is None or self.is_model_exposed(base_model)

    def is_model_exposed(self, model) -> bool:
        model_admin = self.api_site.admin_site._registry.get(model)
        return model_admin is not None and self.is_exposed(model_admin)

    def get_report_description(self, report_class, request) -> str:
        description = getattr(report_class, "report_description", "") or (report_class.__doc__ or "").strip()
        return str(description or report_class.get_report_title())

    def has_report_permission(self, request, report_class) -> bool:
        if not app_settings.report_access_function(request, "view", report_class):
            return False
        model = getattr(report_class, "base_model", None) or report_class.get_report_model()
        return scopes.request_allows(request, model._meta, "view")

    def get_dynamic_report_models(self, request) -> dict:
        """``{model: model_admin}`` a dynamic report may read: the MCP-exposed models the user may view,
        except ``excluded_models`` and the user model (its rows hold password hashes)."""
        user_model = get_user_model()
        return {
            model: model_admin
            for model, model_admin in self.api_site.exposed_admins()
            if model is not user_model
            and not is_excluded(self, model)
            and self.is_exposed(model_admin)
            and model_admin.has_view_or_change_permission(request)
        }

    def get_instructions(self, request) -> str:
        """A catalog of the reports ``request``'s user may run, then the instructions. The catalog drops
        detail (``CATALOG_HEADERS``), then itself, to keep the whole within ``instructions_max_chars``."""
        instructions = super().get_instructions(request)
        if not getattr(getattr(request, "user", None), "is_authenticated", False):
            return instructions
        with self.translation_override(request):
            reports = self.get_reports(request)
            if not reports or len(reports) > self.report_catalog_max:
                return instructions
            entries = [report_entry(self, request, report_class) for report_class in reports]
        for detail, header in CATALOG_HEADERS.items():
            catalog = "\n".join([header, *(catalog_line(entry, detail) for entry in entries)])
            text = f"{catalog}\n\n{instructions}"
            if len(text) <= self.instructions_max_chars:
                return text
        return instructions

    # --- registry ------------------------------------------------------------------------------
    def get_reports(self, request, code=None) -> list:
        reports = report_registry.get_all_reports(admin_site=self.api_site.admin_site.name)
        if code is not None:
            reports = [r for r in reports if r.get_report_code() == code]
        return [r for r in reports if self.is_report_exposed(r) and self.has_report_permission(request, r)]

    def get_report(self, request, code: str):
        reports = self.get_reports(request, code)
        if not reports:
            raise NotFound(f"Unknown report {code!r}; call list_reports for the available codes.")
        return reports[0]

    # --- tools ---------------------------------------------------------------------------------
    def get_tools(self, request=None) -> list:
        return super().get_tools(request) + self.get_report_tools()

    def get_view_tools(self, request=None, *, reserved=()) -> list:
        return super().get_view_tools(request, reserved={*reserved, *REPORT_TOOL_NAMES})

    def get_report_tools(self) -> list:
        max_rows = {
            "type": "integer",
            "minimum": 1,
            "maximum": self.report_max_rows_cap,
            "default": self.report_max_rows,
            "description": "Rows to return. 'totals' and 'row_count' always cover every row.",
        }
        return [
            ToolSpec(
                name="list_reports",
                title="List reports",
                description="The reports you may run: code, title, description, the kind of record it covers "
                "(base_model with its name in base_model_name; say the name), kind (group, series, crosstab "
                "or list), whether it filters by date, 'params' (each parameter that picks records, with the "
                "kind of record its IDs come from), 'balance' (its balance columns include everything before "
                "start_date) and 'columns' (column labels).",
                input_schema=obj({}),
                handler=list_reports,
                annotations=READ_ONLY,
            ),
            ToolSpec(
                name="describe_report",
                title="Describe a report",
                description="A report's parameters as JSON Schema ('params_schema'), its columns, "
                "group by, time series pattern and crosstab field.",
                input_schema=obj({"report": REPORT_ARG}, required=["report"]),
                handler=describe_report,
                annotations=READ_ONLY,
            ),
            ToolSpec(
                name="run_report",
                title="Run a report",
                description="Run a registered report. 'params' takes the report's listed params as lists of "
                "IDs, plus start_date and end_date; describe_report has the full params_schema. Omitted dates "
                "use the report's default range. Returns 'columns', positional 'rows', 'totals' computed over "
                "all rows even when 'truncated' is true, row_count and date_window.",
                input_schema=obj(
                    {
                        "report": REPORT_ARG,
                        "params": {
                            "type": "object",
                            "description": "Report parameters, e.g. {'client_id': [5], 'start_date': '2026-01-01'}.",
                        },
                        "max_rows": max_rows,
                    },
                    required=["report"],
                ),
                handler=run_report,
                annotations=READ_ONLY,
            ),
            ToolSpec(
                name="list_dynamic_report_models",
                title="List models for dynamic reports",
                description="The kinds of record a run_dynamic_report spec may read, with their fields: name, "
                "verbose_name, type, whether it is numeric, a date or a relation, and the related kind of record. "
                "Name each kind of record and field by its verbose_name.",
                input_schema=obj({}),
                handler=list_dynamic_report_models,
                annotations=READ_ONLY,
            ),
            ToolSpec(
                name="run_dynamic_report",
                title="Create and run a report",
                description="Build an ad-hoc report from a JSON spec and run it, when no registered report "
                "answers the question. The spec names a report_model (from list_dynamic_report_models), "
                "kind 'aggregate' (columns computed per group_by value) or 'list' (matching rows), columns "
                "as field paths or {method, field} aggregations, and optionally a date_field with "
                "start_date/end_date, a time_series_pattern with time_series_columns, a crosstab_field "
                "with crosstab_ids and crosstab_columns, and ORM-style filters. Example: {'report_model': "
                "'store.SalesLine', 'group_by': 'client', 'columns': ['name', {'method': 'Sum', 'field': "
                "'value', 'name': 'sales'}], 'date_field': 'date', 'start_date': '2026-03-01', "
                "'end_date': '2026-03-31'}. Only models you may view are allowed. Returns the same shape "
                "as run_report.",
                input_schema=obj({"spec": SPEC_SCHEMA, "max_rows": max_rows}, required=["spec"]),
                handler=dynamic_report,
                annotations=READ_ONLY,
            ),
        ]


def report_kind(report_class) -> str:
    if issubclass(report_class, SlickReportingListViewMixin):
        return "list"
    if report_class.crosstab_field:
        return "crosstab"
    if report_class.time_series_pattern or report_class.time_series_selector:
        return "series"
    return "group"


def model_label(model) -> str | None:
    return f"{model._meta.app_label}.{model._meta.model_name}" if model is not None else None


def model_name(model) -> str | None:
    return str(model._meta.verbose_name) if model is not None else None


def column_name(column) -> str:
    if isinstance(column, (list, tuple)):
        column = column[0]
    return column if isinstance(column, str) else getattr(column, "name", None) or column.__name__


def computation_classes(column):
    """The computation field classes ``column`` names, with every class they require."""
    if isinstance(column, (list, tuple)):
        column = column[0]
    if isinstance(column, str):
        if column not in field_registry.get_all_report_fields_names():
            return
        column = field_registry.get_field_by_name(column)
    if not (isinstance(column, type) and issubclass(column, ComputationField)):
        return
    pending, seen = [column], set()
    while pending:
        klass = pending.pop()
        if klass not in seen:
            seen.add(klass)
            yield klass
            pending.extend(klass._get_required_classes())


def is_balance_report(report_class) -> bool:
    columns = [
        *(report_class.columns or []),
        *(report_class.time_series_columns or []),
        *(report_class.crosstab_columns or []),
    ]
    return any(issubclass(klass, FirstBalanceField) for column in columns for klass in computation_classes(column))


def record_params(site, view) -> dict:
    """``{param: related model label}`` of the form fields that pick records resolve_entities can find:
    an MCP-exposed model outside ``excluded_models``."""
    return {
        name: model_label(field.queryset.model)
        for name, field in view.get_form_class().base_fields.items()
        if isinstance(field, forms.ModelChoiceField)
        and site.is_model_exposed(field.queryset.model)
        and not is_excluded(site, field.queryset.model)
    }


def params_schema(site, view) -> dict:
    schema = form_object_schema(view.get_form_class(), required=True)
    shown = record_params(site, view)
    schema["properties"] = {
        name: prop
        for name, prop in schema["properties"].items()
        if "x-related-model" not in prop or name in shown
    }
    schema["required"] = [name for name in schema.get("required", []) if name in schema["properties"]]
    schema["properties"].update(view.extra_params or {})
    return schema


def report_view(request, report_class):
    view = report_class()
    view.setup(request)
    return view


def report_entry(site, request, report_class) -> dict:
    """What ``list_reports`` and the instructions catalog say about a report."""
    return {
        "report": report_class.get_report_code(),
        "title": str(report_class.get_report_title()),
        "description": site.get_report_description(report_class, request),
        "base_model": model_label(report_class.base_model),
        "base_model_name": model_name(report_class.base_model),
        "kind": report_kind(report_class),
        "date_filter": bool(report_class.date_field),
        "params": record_params(site, report_view(request, report_class)),
        "balance": is_balance_report(report_class),
        "columns": column_labels(report_class),
    }


def column_labels(report_class) -> list:
    """The labels of the report's columns, time series columns and crosstab columns."""
    columns = [
        *(report_class.columns or []),
        *(report_class.time_series_columns or []),
        *(report_class.crosstab_columns or []),
    ]
    try:
        parsed = ReportGenerator.check_columns(
            report_class,
            list(columns),
            report_class.group_by,
            report_class.get_report_model(),
            container_class=report_class,
            group_by_custom_querysets=report_class.group_by_custom_querysets,
        )
    except (FieldDoesNotExist, ImproperlyConfigured):
        return [column_name(column) for column in columns]
    return [str(column["verbose_name"]) for column in parsed if column["name"] != "__index__"]


def catalog_line(entry, detail="questions") -> str:
    """``code: question; params; balance``, ``code; params`` or ``code``, by ``detail``."""
    line = entry["report"]
    if detail == "questions":
        line += ": " + " ".join(entry["description"].split())
    if detail != "codes" and entry["params"]:
        line += "; " + ", ".join(entry["params"])
    if detail == "questions" and entry["balance"]:
        line += "; balance"
    return line


def _max_rows(site, args) -> int:
    value = args.get("max_rows", site.report_max_rows)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InvalidParams("'max_rows' must be a positive integer.")
    return min(value, site.report_max_rows_cap)


def _report_code(args) -> str:
    code = args.get("report")
    if not isinstance(code, str) or not code:
        raise InvalidParams("'report' is required.")
    return code


def _validation_error(exc: ValidationError, detail: str) -> InvalidParams:
    if not hasattr(exc, "error_dict"):
        return InvalidParams(detail, non_field_errors=list(exc.messages))
    fields = {
        name: [{"message": message, "code": error.code} for error in errors for message in error.messages]
        for name, errors in exc.error_dict.items()
    }
    non_field = [e["message"] for e in fields.pop(NON_FIELD_ERRORS, [])]
    extra = {"fields": fields} if fields else {}
    if non_field:
        extra["non_field_errors"] = non_field
    return InvalidParams(detail, **extra)


# --- handlers: handler(mcp_site, request, arguments) -> dict --------------------------------------
def list_reports(site, request, args) -> dict:
    return {"reports": [report_entry(site, request, report_class) for report_class in site.get_reports(request)]}


def describe_report(site, request, args) -> dict:
    report_class = site.get_report(request, _report_code(args))
    view = report_view(request, report_class)
    return {
        "report": report_class.get_report_code(),
        "title": str(report_class.get_report_title()),
        "description": site.get_report_description(report_class, request),
        "base_model": model_label(report_class.base_model),
        "base_model_name": model_name(report_class.base_model),
        "report_model": model_label(report_class.get_report_model()),
        "report_model_name": model_name(report_class.get_report_model()),
        "kind": report_kind(report_class),
        "group_by": report_class.group_by or None,
        "date_field": report_class.date_field or None,
        "time_series_pattern": report_class.time_series_pattern or None,
        "crosstab_field": report_class.crosstab_field or None,
        "columns": [column_name(c) for c in report_class.columns or []],
        "params_schema": params_schema(site, view),
    }


def check_related_params(site, request, report_class, params) -> None:
    """Raise ``InvalidParams`` when a foreign-key param names a row its model admin hides from the user."""
    errors = {}
    for name, field in report_view(request, report_class).get_form_class().base_fields.items():
        if name not in params or not isinstance(field, forms.ModelChoiceField):
            continue
        opts = field.queryset.model._meta
        model_admin = site.api_site.get_model_admin(opts.app_label, opts.model_name)
        if model_admin is None:
            continue
        visible_field = copy.deepcopy(field)
        visible_field.queryset = model_admin.get_queryset(request)
        try:
            visible_field.clean(params[name])
        except ValidationError as exc:
            errors[name] = exc.error_list
    if errors:
        raise _validation_error(ValidationError(errors), "Invalid report parameters.")


def run_report(site, request, args) -> dict:
    report_class = site.get_report(request, _report_code(args))
    params = args.get("params") or {}
    if not isinstance(params, dict):
        raise InvalidParams("'params' must be an object.")
    max_rows = _max_rows(site, args)
    form_fields = report_view(request, report_class).get_form_class().base_fields
    many = {name for name, field in form_fields.items() if isinstance(field, forms.ModelMultipleChoiceField)}
    params = {
        name: [value] if name in many and not isinstance(value, list) else value for name, value in params.items()
    }
    check_related_params(site, request, report_class, params)
    try:
        full_response = report_class.run(request, params)
    except PermissionDenied as exc:
        raise PermissionDeniedError(gettext("You may not view this report.")) from exc
    except ValidationError as exc:
        raise _validation_error(exc, "Invalid report parameters.") from exc
    return {
        "report": report_class.get_report_code(),
        "title": str(report_class.get_report_title()),
        **compact_response(full_response, max_rows=max_rows),
    }


class AdminScope:
    """The field names each model admin shows ``request``'s user. A dynamic report spec may only use
    those fields; its rows come from each admin's ``get_queryset(request)``."""

    def __init__(self, request, admins):
        self.request = request
        self.admins = admins
        self._visible = {}

    def base_querysets(self) -> dict:
        return {model: model_admin.get_queryset(self.request) for model, model_admin in self.admins.items()}

    def visible_fields(self, model) -> set:
        if model not in self._visible:
            model_admin, request = self.admins[model], self.request
            names, _explicit = detail_fields(model_admin, request, None)
            shown = {
                *names,
                *model_admin.get_readonly_fields(request),
                *(column.name for column in get_columns(model_admin, request) if column.kind == "field"),
                model._meta.pk.name,
            }
            self._visible[model] = shown - set(model_admin.get_exclude(request) or ())
        return self._visible[model]

    def check_path(self, model, path, key, errors) -> None:
        """Record in ``errors`` the first field of ``path`` that its model's admin hides."""
        if not isinstance(path, str) or not path:
            return
        for part in path.split("__"):
            if model not in self.admins:
                return
            try:
                field = model._meta.get_field(part)
            except FieldDoesNotExist:
                return
            if field.name not in self.visible_fields(model):
                message = gettext("Field '%(field)s' of %(model)s is not available.") % {
                    "field": getattr(field, "verbose_name", field.name),
                    "model": model._meta.verbose_name_plural,
                }
                errors.setdefault(key, []).append(ValidationError(message, code="hidden_field"))
                return
            if field.related_model is None:
                return
            model = field.related_model

    def check_computation(self, report_model, column, key, errors) -> None:
        if isinstance(column, dict):
            self.check_path(report_model, column.get("field"), key, errors)
        elif isinstance(column, str):
            for klass in computation_classes(column):
                own_queryset = getattr(klass, "queryset", None)
                field_model = klass.report_model or (own_queryset.model if own_queryset is not None else report_model)
                self.check_path(field_model, klass.calculation_field, key, errors)

    def check_spec(self, spec) -> None:
        """Raise ``InvalidParams`` naming each spec key whose field path uses a field an admin hides."""
        label = str(spec.get("report_model") or "").lower()
        report_model = next((model for model in self.admins if model._meta.label_lower == label), None)
        if report_model is None:
            return
        errors = {}
        for key in ("date_field", "group_by", "crosstab_field"):
            self.check_path(report_model, spec.get(key), key, errors)
        group_by_field = _field_or_none(report_model, spec.get("group_by"))
        column_prefix = ""
        if spec.get("kind") != "list" and getattr(group_by_field, "related_model", None) is not None:
            column_prefix = f"{spec['group_by']}__"
        for column in _as_list(spec.get("columns")):
            if isinstance(column, str) and column not in field_registry.get_all_report_fields_names():
                self.check_path(report_model, f"{column_prefix}{column}", "columns", errors)
            else:
                self.check_computation(report_model, column, "columns", errors)
        for key in ("time_series_columns", "crosstab_columns"):
            for column in _as_list(spec.get(key)):
                self.check_computation(report_model, column, key, errors)
        filters = spec.get("filters")
        for name in filters if isinstance(filters, dict) else ():
            path, _, lookup = name.rpartition("__")
            if lookup not in FILTER_LOOKUPS or not path:
                path = name
            self.check_path(report_model, path, "filters", errors)
        if errors:
            raise _validation_error(ValidationError(errors), "Invalid report spec.")


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _field_or_none(model, path):
    if not isinstance(path, str) or not path:
        return None
    for part in path.split("__"):
        try:
            field = model._meta.get_field(part)
        except FieldDoesNotExist:
            return None
        model = field.related_model
        if model is None:
            break
    return field


def list_dynamic_report_models(site, request, args) -> dict:
    admins = site.get_dynamic_report_models(request)
    scope = AdminScope(request, admins)
    catalog = describe_dynamic_report_models(
        request, allowed_models=list(admins), excluded_models=site.excluded_models
    )
    for entry in catalog:
        visible = scope.visible_fields(apps.get_model(entry["identifier"]))
        entry["fields"] = [field for field in entry["fields"] if field["name"] in visible]
    return {"models": catalog}


def dynamic_report(site, request, args) -> dict:
    spec = args.get("spec")
    if not isinstance(spec, dict):
        raise InvalidParams("'spec' must be an object.")
    max_rows = _max_rows(site, args)
    admins = site.get_dynamic_report_models(request)
    if not admins:
        raise PermissionDeniedError(gettext("You may not view any kind of record a dynamic report could read."))
    scope = AdminScope(request, admins)
    scope.check_spec(spec)
    try:
        full_response = run_dynamic_report(
            spec,
            request,
            allowed_models=list(admins),
            excluded_models=site.excluded_models,
            base_querysets=scope.base_querysets(),
        )
    except PermissionDenied as exc:
        raise PermissionDeniedError(gettext("You may not view one of the kinds of record in this report.")) from exc
    except ValidationError as exc:
        raise _validation_error(exc, "Invalid report spec.") from exc
    return compact_response(full_response, max_rows=max_rows)

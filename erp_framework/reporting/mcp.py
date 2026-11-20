"""
Registered reports and ad-hoc dynamic reports as read-only MCP tools.

Mix :class:`ReportToolsMixin` into a django-admin-api-mcp ``AdminMcpSite`` (``ERPMcpSite`` already
does)::

    class MyMcpSite(ReportToolsMixin, AdminMcpSite):
        report_max_rows = 100

The tools are ``list_reports``, ``describe_report``, ``run_report``, ``list_dynamic_report_models``
and ``run_dynamic_report``. Reports run through django-slick-reporting's headless runner and come back as compact rows plus
server-side totals. This module requires django-admin-api-mcp and django-slick-reporting's headless runner,
compact output and dynamic report; erp_framework itself does not.
"""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import NON_FIELD_ERRORS, FieldDoesNotExist, PermissionDenied, ValidationError

from admin_api import scopes
from admin_api.changelist import get_columns
from admin_api.detail import detail_fields
from admin_api.errors import ApiError, NotFound, PermissionDeniedError
from admin_api.jsonschema import form_object_schema
from admin_api.mcp.sites import DEFAULT_INSTRUCTIONS
from admin_api.mcp.tools import ToolSpec, obj
from slick_reporting.dynamic_report import (
    DYNAMIC_REPORT_SPEC_SCHEMA,
    FILTER_LOOKUPS,
    describe_dynamic_report_models,
    run_dynamic_report,
)
from slick_reporting.helpers import compact_response
from slick_reporting.registry import field_registry
from slick_reporting.views import SlickReportingListViewMixin

from erp_framework.base import app_settings
from erp_framework.reporting.registry import report_registry

REPORT_TOOL_NAMES = frozenset(
    {"list_reports", "describe_report", "run_report", "list_dynamic_report_models", "run_dynamic_report"}
)

REPORT_INSTRUCTIONS = """
6. Reports: call list_reports to see the reports you may run, describe_report for a report's \
parameters, then run_report. Results are compact: 'columns', positional 'rows', and 'totals' \
computed over all rows even when 'truncated' is true. Foreign-key parameters take primary keys of \
the model named in the parameter's 'x-related-model' (look them up with list_objects).
7. When no registered report answers the question, call list_dynamic_report_models for the models \
and fields you may use, then build a report with run_dynamic_report."""

READ_ONLY = {"readOnlyHint": True, "openWorldHint": False}
SPEC_SCHEMA = {k: v for k, v in DYNAMIC_REPORT_SPEC_SCHEMA.items() if k != "$schema"}

REPORT_ARG = {
    "type": "string",
    "description": "Report code exactly as returned by list_reports, '<base_model>.<report_slug>' "
    "(e.g. 'client.balances').",
}


class InvalidParams(ApiError):
    status = 400
    code = "invalid_params"


class ReportToolsMixin:
    """Adds the report tools to an ``AdminMcpSite`` subclass.

    A report is listed and runnable when ``is_report_exposed`` allows it (default: every report
    registered on the API site's admin site), ``report_access_function(request, "view", report)``
    passes, and the token scopes allow ``view`` on the report's base model.
    """

    report_max_rows = 200
    report_max_rows_cap = 1000
    instructions = DEFAULT_INSTRUCTIONS + REPORT_INSTRUCTIONS

    # --- policy hooks (override in a subclass) -------------------------------------------------
    def is_report_exposed(self, report_class) -> bool:
        return True

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
        except the user model (its rows hold password hashes)."""
        user_model = get_user_model()
        return {
            model: model_admin
            for model, model_admin in self.api_site.exposed_admins()
            if model is not user_model
            and self.is_exposed(model_admin)
            and model_admin.has_view_or_change_permission(request)
        }

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
                description="The reports you may run: code, title, description, base model, kind "
                "(group, series, crosstab or list) and whether it filters by date.",
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
                description="Run a registered report. 'params' follows describe_report's params_schema; "
                "omitted dates use the report's default range. Returns columns, rows, totals, "
                "row_count, truncated and date_window.",
                input_schema=obj(
                    {
                        "report": REPORT_ARG,
                        "params": {"type": "object", "description": "Report parameters (see describe_report)."},
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
                description="The models a run_dynamic_report spec may read, with their fields: name, type, "
                "whether it is numeric, a date or a relation, and the related model.",
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


def column_name(column) -> str:
    if isinstance(column, (list, tuple)):
        column = column[0]
    return column if isinstance(column, str) else getattr(column, "name", None) or column.__name__


def params_schema(view) -> dict:
    schema = form_object_schema(view.get_form_class(), required=True)
    schema["properties"].update(view.extra_params or {})
    return schema


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
    return {
        "reports": [
            {
                "report": report_class.get_report_code(),
                "title": str(report_class.get_report_title()),
                "description": site.get_report_description(report_class, request),
                "base_model": model_label(report_class.base_model),
                "kind": report_kind(report_class),
                "date_filter": bool(report_class.date_field),
            }
            for report_class in site.get_reports(request)
        ]
    }


def describe_report(site, request, args) -> dict:
    report_class = site.get_report(request, _report_code(args))
    view = report_class()
    view.setup(request)
    return {
        "report": report_class.get_report_code(),
        "title": str(report_class.get_report_title()),
        "description": site.get_report_description(report_class, request),
        "base_model": model_label(report_class.base_model),
        "report_model": model_label(report_class.get_report_model()),
        "kind": report_kind(report_class),
        "group_by": report_class.group_by or None,
        "date_field": report_class.date_field or None,
        "time_series_pattern": report_class.time_series_pattern or None,
        "crosstab_field": report_class.crosstab_field or None,
        "columns": [column_name(c) for c in report_class.columns or []],
        "params_schema": params_schema(view),
    }


def run_report(site, request, args) -> dict:
    report_class = site.get_report(request, _report_code(args))
    params = args.get("params") or {}
    if not isinstance(params, dict):
        raise InvalidParams("'params' must be an object.")
    max_rows = _max_rows(site, args)
    try:
        full_response = report_class.run(request, params)
    except PermissionDenied as exc:
        raise PermissionDeniedError() from exc
    except ValidationError as exc:
        raise _validation_error(exc, "Invalid report parameters.") from exc
    return {
        "report": report_class.get_report_code(),
        "title": str(report_class.get_report_title()),
        **compact_response(full_response, max_rows=max_rows),
    }


class AdminScope:
    """What each model admin shows ``request``'s user: visible field names and the rows of
    ``get_queryset(request)``. A dynamic report spec is checked and narrowed against it."""

    def __init__(self, request, admins):
        self.request = request
        self.admins = admins
        self._visible = {}

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

    def check_path(self, model, path, key, errors, relations) -> None:
        """Record a hidden field of ``path`` in ``errors`` and each relation it crosses in ``relations``."""
        if not isinstance(path, str) or not path:
            return
        prefix = ""
        for part in path.split("__"):
            if model not in self.admins:
                return
            try:
                field = model._meta.get_field(part)
            except FieldDoesNotExist:
                return
            if field.name not in self.visible_fields(model):
                errors.setdefault(key, []).append(
                    ValidationError(f"Field '{part}' of {model._meta.label} is not available.", code="hidden_field")
                )
                return
            if field.related_model is None:
                return
            model, prefix = field.related_model, f"{prefix}{field.name}__"
            relations.append((prefix, model))

    def check_computation(self, report_model, column, key, errors, relations) -> None:
        if isinstance(column, dict):
            self.check_path(report_model, column.get("field"), key, errors, relations)
        elif isinstance(column, str) and column in field_registry.get_all_report_fields_names():
            pending, seen = [field_registry.get_field_by_name(column)], set()
            while pending:
                klass = pending.pop()
                seen.add(klass)
                field_model = klass.report_model or report_model
                own_relations = relations if field_model is report_model else []
                self.check_path(field_model, klass.calculation_field, key, errors, own_relations)
                pending.extend(required for required in klass._get_required_classes() if required not in seen)

    def row_filters(self, prefix, model) -> dict:
        """``{"<prefix><pk>__in": [...]}`` when the admin queryset holds fewer rows than the default manager."""
        model_admin = self.admins.get(model)
        if model_admin is None:
            return {}
        queryset = model_admin.get_queryset(self.request)
        if queryset.query.where == model._default_manager.all().query.where:
            return {}
        return {f"{prefix}{model._meta.pk.name}__in": list(queryset.values_list("pk", flat=True))}

    def scoped_spec(self, spec) -> dict:
        """Reject spec fields the admins hide and return the spec with their row filters added."""
        label = str(spec.get("report_model") or "").lower()
        report_model = next((model for model in self.admins if model._meta.label_lower == label), None)
        if report_model is None:
            return spec
        errors, relations = {}, []
        for key in ("date_field", "group_by", "crosstab_field"):
            self.check_path(report_model, spec.get(key), key, errors, relations)
        group_by_field = _field_or_none(report_model, spec.get("group_by"))
        column_prefix = ""
        if spec.get("kind") != "list" and getattr(group_by_field, "related_model", None) is not None:
            column_prefix = f"{spec['group_by']}__"
        for column in _as_list(spec.get("columns")):
            if isinstance(column, str) and column not in field_registry.get_all_report_fields_names():
                self.check_path(report_model, f"{column_prefix}{column}", "columns", errors, relations)
            else:
                self.check_computation(report_model, column, "columns", errors, relations)
        for key in ("time_series_columns", "crosstab_columns"):
            for column in _as_list(spec.get(key)):
                self.check_computation(report_model, column, key, errors, relations)
        filters = spec.get("filters")
        for name in filters if isinstance(filters, dict) else ():
            path, _, lookup = name.rpartition("__")
            if lookup not in FILTER_LOOKUPS or not path:
                path = name
            self.check_path(report_model, path, "filters", errors, relations)
        if errors:
            raise _validation_error(ValidationError(errors), "Invalid report spec.")
        if filters is not None and not isinstance(filters, dict):
            return spec
        scoped = dict(filters or {})
        for prefix, model in dict.fromkeys([("", report_model), *relations]):
            for name, pks in self.row_filters(prefix, model).items():
                if name in scoped:
                    values = scoped[name] if isinstance(scoped[name], list) else [scoped[name]]
                    wanted = {str(value) for value in values}
                    pks = [pk for pk in pks if str(pk) in wanted]
                scoped[name] = pks
        return {**spec, "filters": scoped}


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
    catalog = describe_dynamic_report_models(request, allowed_models=list(admins))
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
        raise PermissionDeniedError("You may not view any model a dynamic report could read.")
    try:
        spec = AdminScope(request, admins).scoped_spec(spec)
        full_response = run_dynamic_report(spec, request, allowed_models=list(admins))
    except PermissionDenied as exc:
        raise PermissionDeniedError(str(exc) or None) from exc
    except ValidationError as exc:
        raise _validation_error(exc, "Invalid report spec.") from exc
    return compact_response(full_response, max_rows=max_rows)

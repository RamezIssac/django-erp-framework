"""
Registered reports and ad-hoc dynamic reports as read-only MCP tools.

Mix :class:`ReportToolsMixin` into a django-admin-api-mcp ``AdminMcpSite`` (``ERPMcpSite`` already
does)::

    class MyMcpSite(ReportToolsMixin, AdminMcpSite):
        report_max_rows = 100

The tools are ``list_reports``, ``describe_report``, ``run_report``, ``list_dynamic_report_models``
and ``run_dynamic_report``; docs/source/topics/api.rst ("Reports over MCP") describes them. ``run_report``'s
description carries a catalog of the reports the user may run, and results carry ``help`` lines naming
the next call when rows are cut or none match (``total_columns`` and ``summary_report`` on a report class
shape them; see "Row policy and help lines" in the docs). This module requires django-admin-api-mcp
and django-slick-reporting; erp_framework itself does not.
"""

import copy
import datetime
import difflib
import json
import statistics

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
from django.utils.text import camel_case_to_spaces
from django.utils.translation import gettext

from admin_api import scopes
from admin_api.changelist import get_columns
from admin_api.detail import detail_fields
from admin_api.custom_views import InvalidParams
from admin_api.errors import NotFound, PermissionDeniedError
from admin_api.jsonschema import form_object_schema
from admin_api.mcp.resolve import is_excluded
from admin_api.mcp.sites import DEFAULT_INSTRUCTIONS
from admin_api.mcp.handlers import READ as READ_ONLY
from admin_api.mcp.tools import ToolSpec, obj
from slick_reporting.dynamic_report import (
    DYNAMIC_REPORT_SPEC_SCHEMA,
    FILTER_LOOKUPS,
    REPORTABLE_METHODS,
    TIME_SERIES_DELTAS,
    describe_dynamic_report_models,
    run_dynamic_report,
)
from slick_reporting.fields import ComputationField, FirstBalanceField
from slick_reporting.generator import ReportGenerator
from slick_reporting.helpers import compact_response, get_field_from_query_text
from slick_reporting.registry import field_registry
from slick_reporting.views import SlickReportingListViewMixin

from erp_framework.base import app_settings
from erp_framework.reporting.registry import report_registry

REPORT_TOOL_NAMES = frozenset(
    {"list_reports", "describe_report", "run_report", "list_dynamic_report_models", "run_dynamic_report"}
)

REPORT_INSTRUCTIONS = """
7. Reports: run_report's description lists the reports you may run (else call list_reports). Run one \
with run_report, passing resolve_entities IDs as lists: {'client_id': [5]}; when none fits, \
run_dynamic_report. For a top N, pass order_by ('-key' for highest first) and max_rows. Name reports by \
title, columns by label.
Note: run the report for a kind of record ('sales by client'), not resolve_entities or describe_model, \
because it groups by it.
Note: answer totals and balances with a report, not summed list_objects rows, because hand sums hide \
what the report leaves out."""

# Catalog detail levels, richest first: run_report's description uses the first that fits.
# {dates} is the default date range most reports share; a line names its own only when it differs.
CATALOG_HEADERS = {
    "questions": "Reports you may run, dates {dates} (code: question|shape|params|order_by key=label|"
    "balance = includes all before start_date):",
    "short": "Reports you may run, dates {dates} (code: question|shape|params|order_by keys):",
    "params": "Reports you may run, dates {dates} (code|shape|params|order_by keys; list_reports has the questions):",
    "codes": "Reports you may run (codes; list_reports has questions, params and order_by keys):",
}

RUN_REPORT_DESCRIPTION = (
    "Run a registered report. The reports below (or list_reports) show each report's shape, params, order_by "
    "keys and default dates: run one directly; describe_report only adds its columns. Everything but "
    "'report' is optional: 'params' takes the listed params as lists of IDs (omitted: every record) plus "
    "start_date and end_date as YYYY-MM-DD; 'order_by' takes one listed key, '-key' for highest first "
    "(omitted: the report's own order); with max_rows it gives a top N. Returns 'columns', positional "
    "'rows', 'totals' computed over all rows even when 'truncated' is true, row_count, date_window and, "
    "when rows are cut or none match, 'help' with the next call."
)

SPEC_SCHEMA = {k: v for k, v in DYNAMIC_REPORT_SPEC_SCHEMA.items() if k != "$schema"}
SPEC_GUIDE = (
    "kind 'aggregate' (default) computes columns per group_by value, 'list' returns matching rows. columns are "
    f"field paths or {{method, field, name}} aggregations, method one of {', '.join(sorted(REPORTABLE_METHODS))} "
    "(Count on the primary key, e.g. 'id', counts rows); optional: date_field with start_date/end_date, "
    f"time_series_pattern ({', '.join(sorted(TIME_SERIES_DELTAS))}) with time_series_columns, "
    "crosstab_field with crosstab_columns (both lists of {method, field, name}), "
    "filters {'<field path>__<lookup>': value}."
)
SALES = {"method": "Sum", "field": "value", "name": "sales"}
SPEC_EXAMPLE = {
    "report_model": "store.SalesLine",
    "group_by": "client",
    "columns": ["name", SALES],
    "date_field": "date",
    "start_date": "2026-01-01",
    "end_date": "2026-03-31",
    "time_series_pattern": "monthly",
    "time_series_columns": [SALES],
}
RUN_DYNAMIC_REPORT_DESCRIPTION = (
    "Build an ad-hoc report from a spec and run it, when no registered report answers the question. Returns "
    "the same shape as run_report; with group_by, each row starts with its group's label. Next to spec, order_by "
    "takes a column name ('-name' for highest first); with max_rows it gives a top N. "
    f"Spec: {SPEC_GUIDE} Example: {json.dumps(SPEC_EXAMPLE)}"
)
# Dynamic catalog detail levels, richest first: run_dynamic_report's description uses the first that fits.
DYNAMIC_CATALOG_HEADERS = {
    "fields": "Kinds of record you may report on (report_model (name): fields | description; # number, @ date, "
    "> relation to):",
    "reportable": "Kinds of record you may report on (report_model (name): number #, date @ and relation > fields "
    "| description; list_dynamic_report_models has the rest):",
    "models": "Kinds of record you may report on (report_model (name) | description; list_dynamic_report_models "
    "has their fields):",
    "names": "Kinds of record you may report on (list_dynamic_report_models has their fields and descriptions):",
}

# list_reports fields: the defaults route a question to a run, the others come with 'fields'.
DEFAULT_ENTRY_FIELDS = ("report", "question", "params", "order_by")
CATALOG_ENTRY_FIELDS = ("report", "description", "question", "shape", "params", "order_by", "balance", "dates")

REPORT_ARG = {
    "type": "string",
    "description": "Report code exactly as listed in run_report's description or by list_reports "
    "(e.g. 'client.balances'). "
    "Tell the user the report's title, not its code.",
}


class ReportToolsMixin:
    """Adds the report tools to an ``AdminMcpSite`` subclass.

    A report is listed and runnable when ``is_report_exposed`` allows it (default: its base model's
    admin is exposed through MCP), ``report_access_function(request, "view", report)`` passes, and the
    token scopes allow ``view`` on the report's base model.
    """

    report_max_rows = 50
    report_max_rows_cap = 1000
    report_summary_rows = 10
    report_catalog_max = 40
    # Claude Code keeps 4,096 characters of a tool description (16,384 once loaded through tool search).
    report_tool_description_max_chars = 4096
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

    def get_report_question(self, report_class, request) -> str:
        """The short catalog question (5 to 8 words): ``report_question``, else the title."""
        return str(getattr(report_class, "report_question", "") or report_class.get_report_title())

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

    def get_report_catalog(self, request, room: int) -> str:
        """The reports ``request``'s user may run, at the richest ``CATALOG_HEADERS`` level that fits in
        ``room`` characters; empty without a user, above ``report_catalog_max`` or when none fits."""
        if not getattr(getattr(request, "user", None), "is_authenticated", False):
            return ""
        with self.translation_override(request):
            reports = self.get_reports(request)
            if not reports or len(reports) > self.report_catalog_max:
                return ""
            entries = [report_entry(self, request, report_class, CATALOG_ENTRY_FIELDS) for report_class in reports]
        dates = statistics.mode(entry["dates"] for entry in entries)
        for entry in entries:
            entry["dates"] = None if entry["dates"] == dates else entry["dates"]
        headers = {detail: header.format(dates=dates) for detail, header in CATALOG_HEADERS.items()}
        return fit_catalog(headers, catalog_line, entries, room)

    def get_dynamic_report_catalog(self, request, room: int) -> str:
        """The kinds of record and fields ``request``'s user may put in a dynamic report spec, at the richest
        ``DYNAMIC_CATALOG_HEADERS`` level that fits in ``room`` characters; empty without a user, models or fit."""
        if not getattr(getattr(request, "user", None), "is_authenticated", False):
            return ""
        with self.translation_override(request):
            models = list_dynamic_report_models(self, request, {})["models"]
        return fit_catalog(DYNAMIC_CATALOG_HEADERS, dynamic_catalog_line, models, room) if models else ""

    # --- registry ------------------------------------------------------------------------------
    def get_reports(self, request, code=None) -> list:
        reports = report_registry.get_all_reports(admin_site=self.api_site.admin_site.name)
        if code is not None:
            reports = [r for r in reports if r.get_report_code() == code]
        return [r for r in reports if self.is_report_exposed(r) and self.has_report_permission(request, r)]

    def get_report(self, request, code: str):
        reports = self.get_reports(request, code)
        if reports:
            return reports[0]
        codes = [report_class.get_report_code() for report_class in self.get_reports(request)]
        closest = difflib.get_close_matches(code, codes, n=1)
        help_line = (
            gettext("Closest report: run_report(report='%(code)s').") % {"code": closest[0]}
            if closest
            else gettext("Call list_reports for the codes you may run.")
        )
        raise NotFound(f"Unknown report {code!r}; call list_reports for the available codes.", help=[help_line])

    # --- tools ---------------------------------------------------------------------------------
    def get_tools(self, request=None) -> list:
        return super().get_tools(request) + self.get_report_tools(request)

    def get_tool(self, name: str, request=None):
        """Look a tool up by name without building the per-user catalogs of the report tool descriptions."""
        tools = self.get_report_tools() if name in REPORT_TOOL_NAMES else super().get_tools(request)
        return next((tool for tool in tools if tool.name == name), None)

    def get_view_tools(self, request=None, *, reserved=()) -> list:
        return super().get_view_tools(request, reserved={*reserved, *REPORT_TOOL_NAMES})

    def get_report_tools(self, request=None) -> list:
        room = self.report_tool_description_max_chars - len(RUN_REPORT_DESCRIPTION) - 2
        catalog = self.get_report_catalog(request, room)
        dynamic_room = self.report_tool_description_max_chars - len(RUN_DYNAMIC_REPORT_DESCRIPTION) - 2
        dynamic_catalog = self.get_dynamic_report_catalog(request, dynamic_room)
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
                description="The reports you may run, when run_report's description lists none: code "
                "('report'), 'question', 'params' (each parameter that picks records, with the kind of record "
                "its IDs come from) and 'order_by' (the keys run_report sorts by, with labels). 'fields' adds "
                "more; 'balance' means balance columns include everything before start_date.",
                input_schema=obj(
                    {
                        "fields": {
                            "type": "array",
                            "items": {"enum": [name for name in ENTRY_FIELDS if name not in DEFAULT_ENTRY_FIELDS]},
                        }
                    }
                ),
                handler=list_reports,
                annotations=READ_ONLY,
            ),
            ToolSpec(
                name="describe_report",
                title="Describe a report",
                description="A report's columns and its parameters as JSON Schema ('params_schema'), plus the "
                "group by, time series pattern and crosstab field its run_report line shows as shape.",
                input_schema=obj({"report": REPORT_ARG}, required=["report"]),
                handler=describe_report,
                annotations=READ_ONLY,
            ),
            ToolSpec(
                name="run_report",
                title="Run a report",
                description=f"{RUN_REPORT_DESCRIPTION}\n\n{catalog}" if catalog else RUN_REPORT_DESCRIPTION,
                input_schema=obj(
                    {
                        "report": REPORT_ARG,
                        "params": {
                            "type": "object",
                            "description": "Report parameters, e.g. {'client_id': [5], 'start_date': '2026-01-01'}.",
                        },
                        "order_by": {
                            "type": "string",
                            "description": "An order_by key of the report, e.g. '-__balance__' for highest first.",
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
                "verbose_name, type, whether it is numeric, a date or a relation, and the related kind of record; "
                "plus the spec grammar ('spec_schema', 'spec_guide', 'spec_example'). Name each kind of record "
                "and field by its verbose_name.",
                input_schema=obj({}),
                handler=list_dynamic_report_models,
                annotations=READ_ONLY,
            ),
            ToolSpec(
                name="run_dynamic_report",
                title="Create and run a report",
                description=f"{RUN_DYNAMIC_REPORT_DESCRIPTION}\n\n{dynamic_catalog}"
                if dynamic_catalog
                else f"{RUN_DYNAMIC_REPORT_DESCRIPTION} list_dynamic_report_models gives the kinds of record.",
                input_schema=obj(
                    {
                        "spec": {"type": "object", "description": "The report spec ('spec_schema')."},
                        "order_by": {
                            "type": "string",
                            "description": "A column name of the result, e.g. '-sales' for highest first.",
                        },
                        "max_rows": max_rows,
                    },
                    required=["spec"],
                ),
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
    return model._meta.label_lower if model is not None else None


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


def all_columns(report_class) -> list:
    """The report's columns, time series columns and crosstab columns."""
    return [
        *(report_class.columns or []),
        *(report_class.time_series_columns or []),
        *(report_class.crosstab_columns or []),
    ]


def is_balance_report(report_class) -> bool:
    return any(
        issubclass(klass, FirstBalanceField)
        for column in all_columns(report_class)
        for klass in computation_classes(column)
    )


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


def report_shape(report_class) -> str:
    """The catalog's shape of the report's rows: 'list', else 'by <group_by>', 'x <crosstab_field>' and the
    time series pattern."""
    kind = report_kind(report_class)
    parts = [
        f"by {report_class.group_by}" if report_class.group_by else "",
        f"x {report_class.crosstab_field}" if report_class.crosstab_field else "",
        str(report_class.time_series_pattern or ("series" if kind == "series" else "")),
    ]
    return " ".join(part for part in parts if part) or kind


def default_dates(request, report_class) -> str:
    """The start_date and end_date a run takes when params omit them, e.g. '2026-01-01 to today'."""
    if not (report_class.date_field or (report_class.start_date_field_name and report_class.end_date_field_name)):
        return "all"
    view = report_view(request, report_class)
    initial, fields = view.get_initial(), view.get_form_class().base_fields
    bounds = []
    for name in ("start_date", "end_date"):
        value = initial.get(name, fields[name].initial) if name in fields else None
        value = value() if callable(value) else value
        value = value.date() if isinstance(value, datetime.datetime) else value
        bounds.append("today" if value == datetime.date.today() else str(value or "any"))
    return " to ".join(bounds)


def report_entry(site, request, report_class, fields) -> dict:
    """What ``list_reports`` and the run_report catalog say about a report: ``fields`` of ``ENTRY_FIELDS``."""
    return {name: ENTRY_FIELDS[name](site, request, report_class) for name in ENTRY_FIELDS if name in fields}


def parse_columns(report_class, columns) -> list | None:
    """slick's parsed ``columns`` of the report (name, verbose_name, source), or None when they do not parse."""
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
        return None
    return [column for column in parsed if column["name"] != "__index__"]


def column_labels(report_class) -> list:
    """The labels of the report's columns, time series columns and crosstab columns."""
    columns = all_columns(report_class)
    parsed = parse_columns(report_class, columns)
    if parsed is None:
        return [column_name(column) for column in columns]
    return [str(column["verbose_name"]) for column in parsed]


def order_columns(report_class) -> dict:
    """``{key: label}`` of the computed columns slick can sort a grouped report's rows by (not list reports)."""
    if report_kind(report_class) == "list":
        return {}
    parsed = parse_columns(report_class, report_class.columns or []) or []
    return {column["name"]: str(column["verbose_name"]) for column in parsed if column["source"] == "magic_field"}


ENTRY_FIELDS = {
    "report": lambda site, request, report_class: report_class.get_report_code(),
    "title": lambda site, request, report_class: str(report_class.get_report_title()),
    "description": lambda site, request, report_class: site.get_report_description(report_class, request),
    "question": lambda site, request, report_class: site.get_report_question(report_class, request),
    "base_model": lambda site, request, report_class: model_label(report_class.base_model),
    "base_model_name": lambda site, request, report_class: model_name(report_class.base_model),
    "kind": lambda site, request, report_class: report_kind(report_class),
    "shape": lambda site, request, report_class: report_shape(report_class),
    "dates": lambda site, request, report_class: default_dates(request, report_class),
    "date_filter": lambda site, request, report_class: bool(report_class.date_field),
    "params": lambda site, request, report_class: record_params(site, report_view(request, report_class)),
    "balance": lambda site, request, report_class: is_balance_report(report_class),
    "columns": lambda site, request, report_class: column_labels(report_class),
    "order_by": lambda site, request, report_class: order_columns(report_class),
}


def catalog_line(entry, detail="questions") -> str:
    """The report's catalog line at ``detail``, one of ``CATALOG_HEADERS``: enough for a plain run. Its
    ``dates`` are None when the header names them."""
    if detail == "codes":
        return entry["report"]
    parts = [entry["report"]]
    if detail in ("questions", "short"):
        text = entry["description"] if detail == "questions" else entry["question"]
        parts = [f"{entry['report']}: {' '.join(text.split())}"]
    parts.append(entry["shape"])
    if entry["params"]:
        parts.append(", ".join(entry["params"]))
    if entry["order_by"]:
        keys = entry["order_by"].items() if detail == "questions" else ((key, None) for key in entry["order_by"])
        parts.append("order_by " + ", ".join(key if label is None else f"{key}={label}" for key, label in keys))
    if detail == "questions" and entry["balance"]:
        parts.append("balance")
    if entry["dates"]:
        parts.append(f"dates {entry['dates']}")
    return "|".join(parts)


def dynamic_catalog_line(entry, detail) -> str:
    """A kind of record's line in run_dynamic_report's description at ``detail``, one of ``DYNAMIC_CATALOG_HEADERS``;
    the name only when it is not the model's own name in words."""
    line = entry["identifier"]
    if entry["verbose_name"].lower() != camel_case_to_spaces(line.rpartition(".")[2]):
        line += f" ({entry['verbose_name']})"
    if detail == "names":
        return line
    names = []
    for field in entry["fields"] if detail != "models" else ():
        relation = f">{field['related_model']}" if field["is_relation"] else ""
        mark = "#" if field["is_numeric"] else "@" if field["is_date"] else relation
        if detail == "fields" or mark:
            names.append(field["name"] + mark)
    line = f"{line}: {', '.join(names)}" if names else line
    description = entry.get("description")
    return f"{line} | {' '.join(description.split())}" if description else line


def fit_catalog(headers, line, entries, room) -> str:
    """The first of ``headers`` (richest first) whose catalog of ``line(entry, detail)`` fits in ``room``, else ""."""
    for detail, header in headers.items():
        catalog = "\n".join([header, *(line(entry, detail) for entry in entries)])
        if len(catalog) <= room:
            return catalog
    return ""


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
    extra = args.get("fields") or []
    unknown = [name for name in extra if name not in ENTRY_FIELDS] if isinstance(extra, list) else [extra]
    if unknown:
        known = ", ".join(name for name in ENTRY_FIELDS if name not in DEFAULT_ENTRY_FIELDS)
        raise InvalidParams(f"Unknown fields {unknown!r}.", help=[f"'fields' takes any of: {known}."])
    fields = {*DEFAULT_ENTRY_FIELDS, *extra}
    return {
        "reports": [report_entry(site, request, report_class, fields) for report_class in site.get_reports(request)]
    }


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


def fixed_call(code, **args) -> str:
    """A run_report call to retry with, for an error's ``help``."""
    return "run_report(" + ", ".join(f"{name}={value!r}" for name, value in {"report": code, **args}.items()) + ")"


def params_help(view, code, params, error: InvalidParams) -> list:
    """``help`` for refused params: the closest name for an unknown one, the ID list shape for a bad ID."""
    form_fields = view.get_form_class().base_fields
    known = [*form_fields, *(view.extra_params or {})]
    lines = []
    for name, errors in error.extra.get("fields", {}).items():
        if any(e["code"] == "unknown_parameter" for e in errors):
            closest = difflib.get_close_matches(name, known, n=1)
            if closest:
                lines.append(fixed_call(code, params={closest[0]: params[name]}))
            else:
                lines.append(gettext("Parameters of this report: %(names)s.") % {"names": ", ".join(known)})
        elif isinstance(form_fields.get(name), forms.ModelChoiceField):
            lines.append(fixed_call(code, params={name: ["<id from resolve_entities>"]}))
    return lines


def run_report_help(site, request, report_class, result, params, order_by) -> list:
    """The next calls when none match or the default ``max_rows`` cut the rows, from the report's order_by
    keys, params and ``summary_report``."""
    if result["row_count"] == 0:
        window = result["date_window"]
        lines = [gettext("No rows match.")]
        if window["start"] or window["end"]:
            lines.append(gettext("Widen start_date and end_date in params (now: %(window)s).") % {"window": window["label"]})
        picked = [name for name in params if name in record_params(site, report_view(request, report_class))]
        if picked:
            lines.append(gettext("Or drop the %(names)s filter.") % {"names": ", ".join(picked)})
        return lines
    if not result["truncated"]:
        return []
    code = report_class.get_report_code()
    lines = []
    keys = order_columns(report_class)
    if keys and not order_by:
        lines.append(
            gettext("For a top N pass order_by='-%(key)s' and max_rows=<n> (order_by keys: %(keys)s).")
            % {"key": next(iter(keys)), "keys": ", ".join(keys)}
        )
    record = record_params(site, report_view(request, report_class))
    base = model_label(report_class.base_model)
    name = next((name for name, label in record.items() if label == base), next(iter(record), None))
    if name and name not in params:
        lines.append(
            gettext("For one record pass params {'%(name)s': [<id>]} with an ID from resolve_entities.")
            % {"name": name}
        )
    summary = getattr(report_class, "summary_report", None)
    if summary is not None and not isinstance(summary, str):
        summary = summary.get_report_code()
    summary_class = next(iter(site.get_reports(request, summary)), None) if summary and summary != code else None
    if summary_class is not None:
        lines.append(
            gettext("For totals run %(code)s (%(title)s).")
            % {"code": summary, "title": summary_class.get_report_title()}
        )
    if len(result["rows"]) < site.report_max_rows_cap:
        lines.append(gettext("For more rows pass max_rows (up to %(cap)s).") % {"cap": site.report_max_rows_cap})
    return lines


def check_order_by(order_by, keys, retry=None) -> None:
    """Raise ``InvalidParams`` unless ``order_by`` is one of ``keys``, '-' prefixed for highest first; its
    ``help`` is ``retry(key)`` with the closest key, given ``retry``."""
    if isinstance(order_by, str) and order_by.removeprefix("-") in keys:
        return
    message = (
        gettext("Sort by one of: %(keys)s; prefix '-' for highest first.") % {"keys": ", ".join(keys)}
        if keys
        else gettext("This report cannot be sorted.")
    )
    error = InvalidParams("Invalid report parameters.", fields={"order_by": [{"message": message, "code": "invalid"}]})
    if retry:
        closest = difflib.get_close_matches(str(order_by).removeprefix("-"), keys, n=1, cutoff=0)
        error.extra["help"] = [retry(f"-{closest[0]}" if closest else None)]
    raise error


def run_report(site, request, args) -> dict:
    report_class = site.get_report(request, _report_code(args))
    code = report_class.get_report_code()
    params = args.get("params") or {}
    if not isinstance(params, dict):
        raise InvalidParams("'params' must be an object.")
    max_rows = _max_rows(site, args)
    view = report_view(request, report_class)
    form_fields = view.get_form_class().base_fields
    many = {name for name, field in form_fields.items() if isinstance(field, forms.ModelMultipleChoiceField)}
    params = {
        name: [value] if name in many and not isinstance(value, list) else value for name, value in params.items()
    }
    try:
        check_related_params(site, request, report_class, params)
    except InvalidParams as error:
        error.extra["help"] = params_help(view, code, params, error)
        raise
    order_by = args.get("order_by") or ""
    if order_by:
        check_order_by(
            order_by, order_columns(report_class), lambda key: fixed_call(code, **({"order_by": key} if key else {}))
        )
    try:
        full_response = report_class.run(
            request, params, max_rows=max_rows, **({"default_order_by": order_by} if order_by else {})
        )
    except PermissionDenied as exc:
        raise PermissionDeniedError(gettext("You may not view this report.")) from exc
    except ValidationError as exc:
        error = _validation_error(exc, "Invalid report parameters.")
        error.extra["help"] = params_help(view, code, params, error)
        raise error from exc
    result = compact_response(full_response, max_rows=max_rows)
    cut_by_default = result["truncated"] and "max_rows" not in args
    if cut_by_default and report_kind(report_class) == "list" and getattr(report_class, "total_columns", None):
        result["rows"] = result["rows"][: site.report_summary_rows]
    help_lines = run_report_help(site, request, report_class, {**result, "truncated": cut_by_default}, params, order_by)
    return {
        "report": code,
        "title": str(report_class.get_report_title()),
        **result,
        **({"help": help_lines} if help_lines else {}),
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
                *(field.name for field in model._meta.concrete_fields if field.primary_key),
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
        try:
            group_by_model = get_field_from_query_text(spec.get("group_by"), report_model).related_model
        except (AttributeError, FieldDoesNotExist):
            group_by_model = None
        column_prefix = f"{spec['group_by']}__" if spec.get("kind") != "list" and group_by_model else ""
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


def list_dynamic_report_models(site, request, args) -> dict:
    admins = site.get_dynamic_report_models(request)
    scope = AdminScope(request, admins)
    catalog = describe_dynamic_report_models(
        request, allowed_models=list(admins), excluded_models=site.excluded_models
    )
    for entry in catalog:
        model = apps.get_model(entry["identifier"])
        visible = scope.visible_fields(model)
        entry["fields"] = [field for field in entry["fields"] if field["name"] in visible]
        description = site.get_model_description(admins[model], request)
        if description:
            entry["description"] = description
    return {"models": catalog, "spec_schema": SPEC_SCHEMA, "spec_guide": SPEC_GUIDE, "spec_example": SPEC_EXAMPLE}


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
        error = _validation_error(exc, "Invalid report spec.")
        fields = error.extra.get("fields", {})
        unknown = [key for key, errors in fields.items() if any(e["code"] == "unknown_field" for e in errors)]
        if unknown:
            error.extra["help"] = [corrected_spec_help(spec, unknown)]
        raise error from exc
    order_by = args.get("order_by")
    if order_by:
        check_order_by(order_by, [c["name"] for c in full_response["columns"] if c.get("visible", True) is not False])
        data, descending = full_response["data"], order_by.startswith("-")
        values = data[order_by.removeprefix("-")]
        filled, empty = [], []
        for index, value in enumerate(values):
            (empty if value in (None, "") else filled).append(index)
        order = sorted(filled, key=values.__getitem__, reverse=descending) + empty
        full_response["data"] = {name: [column[index] for index in order] for name, column in data.items()}
    return compact_response(full_response, max_rows=max_rows)


def corrected_spec_help(spec, keys) -> str:
    """``help`` for ``unknown_field`` errors on ``keys``: the spec with each name in time_series_columns or
    crosstab_columns swapped for the ``columns`` aggregation of that name, else a Sum of that field."""
    named = {column.get("name"): column for column in _as_list(spec.get("columns")) if isinstance(column, dict)}
    fixed = dict(spec)
    for key in {"time_series_columns", "crosstab_columns"}.intersection(keys):
        fixed[key] = [
            named.get(column, {"method": "Sum", "field": column, "name": column})
            if isinstance(column, str) and column not in field_registry.get_all_report_fields_names()
            else column
            for column in _as_list(spec[key])
        ]
    if fixed == spec:
        return gettext("list_dynamic_report_models gives the fields of each kind of record.")
    return f"run_dynamic_report(spec={json.dumps(fixed)})"

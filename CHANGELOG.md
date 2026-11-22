# Changelog
All notable changes to this project are/will be documented in this file.

## [Unreleased]
### Added
- `erp_framework.reporting.mcp.ReportToolsMixin`, mixed into `ERPMcpSite`: read-only MCP tools `list_reports`, `describe_report`, `run_report`, `list_dynamic_report_models` and `run_dynamic_report`, scoped by `report_access_function`, token scopes and each model admin's `get_queryset(request)` and shown fields. They need django-slick-reporting's headless runner, `compact_response` and `dynamic_report`; without them `ERPMcpSite` publishes the admin tools only. See the API docs, "Reports over MCP".
- The report tools' server instructions send foreign-key report parameters to `resolve_entities` with `models` set to the parameter's model (`params` in `list_reports`, `x-related-model` in `describe_report`).
- `run_dynamic_report` and `list_dynamic_report_models` honour the MCP site's `excluded_models` (also passed to slick as `excluded_models`).
- `list_objects` rows of entity admins carry `name`: `EntityAdmin.get_list_display` swaps `get_enhanced_obj_title` for `name` on API and MCP requests.
- `list_reports` and `describe_report` return `base_model_name` (and `report_model_name`), the verbose names next to the model paths; `list_dynamic_report_models` entries already carry `verbose_name`.
- The report tools' instructions ask the agent to name reports by title, columns by label, kinds of record by name and records by label.
- `list_reports` entries carry `params` (each parameter that picks records mapped to its model), `balance` (a column adds everything before `start_date`), `columns` (the column labels) and `question` (`report_question`, a 5 to 8 word question for the catalog, else the title; hook `get_report_question`). Parameters whose model is not exposed through MCP, or is in the site's `excluded_models`, are left out of `params` and of `describe_report`'s `params_schema`.
- `run_report`'s description ends with a catalog of the reports the user may run (`get_report_catalog(request, room)`), at most `report_catalog_max` (40) lines, at the richest detail level that keeps the description within `report_tool_description_max_chars` (4096).
- `run_report` reads a single ID for a list-of-IDs parameter as a one-item list.
- `run_report` row policy: `max_rows` defaults to 50 (`report_max_rows`) and goes to slick's `run(max_rows=...)`: a list report builds at most that many rows and counts and totals all rows in the database. A report may declare slick's `total_columns` (the columns `totals` covers; list reports returned `totals: {}`) and `summary_report` (the code or class of the report that aggregates its rows). A list report with `total_columns` run without `max_rows` over more than `report_max_rows` rows returns its totals and first `report_summary_rows` (10) rows.
- `run_report` results and errors carry `help` lines naming the next call when no row matches, the default `max_rows` cut the rows, or a report code, parameter, ID or `order_by` key is wrong (see the API docs, "Row policy and help lines").
- `list_reports` returns `report`, `question`, `params` and `order_by` by default; its `fields` argument adds `title`, `description`, `base_model`, `base_model_name`, `kind`, `shape`, `date_filter`, `dates`, `balance` and `columns`.
- `list_dynamic_report_models` returns the spec grammar (`spec_schema`, `spec_guide`, `spec_example`); `run_dynamic_report`'s input schema takes `spec` as a plain object.
- `run_dynamic_report`'s description carries the spec grammar (aggregation methods, time series patterns), the spec example and the models and fields the user may read (`get_dynamic_report_catalog(request, room)`), at the richest detail level that fits `report_tool_description_max_chars`: a dynamic question needs no discovery call.
- `run_report` takes `order_by`: one of the report's computed column keys (`list_reports` `order_by`, e.g. `-__balance__` for highest first), passed to slick as `default_order_by`; with `max_rows` it gives a top N. List reports and other keys are refused with the accepted keys. The catalog lines carry the keys (with labels at the description level).
- Report tool messages use verbose names and no model paths: a hidden field reads "Field 'Value' of Sales is not available.", and permission refusals carry a plain `detail` ("You may not view this report.").
- `run_dynamic_report` takes `order_by`: a result column name, `-name` for highest first, empty cells last; with `max_rows` it gives a top N. Its description states it, and its spec example is a monthly time series with `time_series_columns` given as `{method, field, name}` objects.
- A `run_dynamic_report` `unknown_field` error carries `help` with the corrected call: each name in `time_series_columns` or `crosstab_columns` becomes the `columns` aggregation of that name, else a `Sum` of that field.
- `run_report`'s catalog lines carry the report's shape (`by client monthly`, `by client x product`, `list`) and its header the default dates most reports share (`dates 2026-01-01 to today`); a report with other default dates names them on its line. `list_reports` `fields` adds `shape` and `dates`. `run_dynamic_report`'s description says each group_by row starts with its group's label (django-slick-reporting PR 134).
- `run_dynamic_report`'s catalog lines end with each model's description (the site's `get_model_description`, one line), also in `list_dynamic_report_models` entries; the levels without all fields keep the descriptions, the last level drops them. A line names the model's verbose name only when it is not the model name in words.
- `run_report`'s catalog lines are `code: question|shape|params|order_by keys`: `|` without spaces and the params without a `params` label. 27 reports with 8-word questions fit the 4096-character description at the question level.
- The report instructions are one routing item: run a report listed in `run_report`'s description with `resolve_entities` IDs, else `run_dynamic_report`; answer totals and balances with a report, not summed `list_objects` rows.

### Fixed
- Dynamic reports accept `Count` on `id` for a multi-table inheritance child: every concrete primary key field, the parent's included, counts as shown by the admin.
- `run_report`'s empty-result help names an open-ended date window by slick's label ("now: From 2001-01-01", "now: As of 2001-01-31"); it read "now 2001-01-01 to " with `end_date` null and gave no widen line with `start_date` null.
- A tool call looks its tool up by name without building the per-user catalogs of the `run_report` and `run_dynamic_report` descriptions (`ReportToolsMixin.get_tool`).

## [1.8.0] - 2026-11-19
### Security
- Report `_export=csv` and `_export=print` requests require the report's `export` / `print` permission through `report_access_function`; a denied request gets HTTP 403. Other `_export` actions require `export`.
- Report URLs are wrapped in the admin site's `admin_view`: non-staff users are redirected to the admin login, and a custom `admin_site_access_permission` now applies to reports.
- `admin_site_access_permission` requires an active staff user in every mode; `DEBUG=True` no longer admits every authenticated user.
- `EntityAdmin.get_by_slug` requires view or change permission on the model (HTTP 403 otherwise) and looks the object up through `get_queryset(request)`.
- Entity names are HTML-escaped in the admin changelist title and statistics columns (`get_enhanced_obj_title`, `get_stats_icon`), both built with `format_html`. Thanks to p-w for the fix ([#63](https://github.com/RamezIssac/django-erp-framework/pull/63)).
- Removed the unused `erp_framework/print_base.html` template.

### Added
- `erp_framework.docs` (label `erp_docs`): an in-app user guide of Markdown pages rendered per request for logged-in staff, no build step. Pages come from installed apps' `docs/` directories plus `ERP_DOCS_SOURCE_DIRS` (later sources shadow earlier ones). They support YAML front-matter (`title`, `order`, `perms` with any-of semantics; no perms = staff-only; denied URLs answer 404), a per-language subdirectory, and images/files served through the same gated view. Whole-guide access is set with `ERP_DOCS_ACCESS_FUNCTION` (mirrors `report_access_function`).
- `erp_docs` pages render in a standalone full-page layout: a left sidebar with the docs page list, a slim top bar with the guide title and a "Back to the application" link, the jazzy_tabler admin's Tabler/Bootstrap 5 assets and theme mode, RTL-aware and responsive. Override `erp_docs/base.html` blocks (`title`, `branding`, ...) to brand it.
- "User guide" link (book icon, `ERP_DOCS_TITLE` label, new tab) in the admin top navbar for users who pass the docs access function, when `erp_docs` is installed and `erp_framework.admin.jazzy_tabler_integration` is active. It uses django-jazzy-tabler's `navbar_extra` hook (`jazzy_tabler/includes/navbar_extra.html`); disable with `ERP_DOCS_SHOW_ADMIN_LINK = False`.
- `erp_framework.admin.prepopulated`: `PrepopulatedInlineMixin` (one inline row per entity, locked sheet, read-only entity widget, live computed fields, sticky totals, Enter-as-Tab) and `HeaderLookupAdminMixin` (htmx redirect to an existing document when its header is chosen). Ships htmx 2.0.4.
- Prepopulated sheets behave like a spreadsheet: arrow keys move between cells/rows (RTL aware), Enter/Shift+Enter, PageUp/PageDown, Ctrl+Up/Down, F2 to edit in a cell, Escape to revert. Numeric cells are `inputmode="decimal"` text inputs (arrows/wheel never change values), the header row and entity column are frozen, and a keyboard-shortcuts note shows under the sheet.
- `PrepopulatedInlineMixin.fast_rendering` (default on for locked sheets): lean grid template with rows rendered in Python (`erp_grid` tag). A 526-row journal renders in ~0.3 s / 1.6 MB instead of ~1.1 s / 6.4 MB.
- `PrepopulatedInlineMixin.autosave` + `GridAutosaveAdminMixin`: each row is saved (htmx) when a cell is committed, through the admin's own `save_formset`; on the add page the first save creates the document.
- `erp_framework.api.erp_api_site`: an optional JSON API over `erp_admin_site` through django-admin-api-mcp (`admin_api`), with the same permissions, forms, inlines and actions as the admin. Requires `django-admin-api-mcp` (import name `admin_api`); erp_framework itself does not.
- `erp_framework.api.erp_mcp_site`: MCP access to the ERP admins for AI agents (`django-admin-api-mcp`), with the same permissions and hooks as the admin and the JSON API. The `changeform_saved` signal also sends `request=request`, so receivers can skip side effects during an MCP dry run (`request.is_dry_run`).
- `EntityAdmin.process_changeform(request, obj, change)`: validation and saving (`whole_changeform_validation`, `pre_save`, `save_model`, `save_related`, `post_save`, `changeform_saved`, LogEntry) extracted from `_changeform_view`; it returns a `ChangeformResult` and is the pipeline the JSON API and MCP writes run.
- `description` on every framework admin base (`EntityAdmin`, `TransactionAdmin`, the prepopulated admins and the activity `LogEntryAdmin`) through the new `DescriptionMixin`; each passes it to the changelist context, `None` by default.

### Changed
- Requires `django-slick-reporting>=1.5.1`.
- New dependencies: `markdown-it-py`, `mdit-py-plugins`, `PyYAML` (for `erp_docs`).
- Requires `django-jazzy-tabler>=0.3.0`, which ships the `navbar_extra` hook used by the User guide link.
- The jazzy_tabler integration no longer ships its own `admin/base.html` (a copy of the theme's 0.1.1 template); the theme's `base.html` is used.
- `PrepopulatedAdmin` / `RaPrePopulatedAdmin` are deprecated (they override Django's private `_create_formsets`); use `PrepopulatedInlineMixin`.
- Saving a prepopulated sheet never duplicates rows: a new row whose entity is already saved updates that item.
- Read the Docs build modernized (Ubuntu 24.04, Python 3.12, Sphinx 8.2.3); the package is installed from the checkout.

### Fixed
- `erp_framework/js/select2_compat.js` (listed in `EntityAdmin.Media`) was missing from the repository, which made admin pages raise "Missing staticfiles manifest entry" (HTTP 500) under `ManifestStaticFilesStorage`.
- The admin layout with django-jazzy-tabler 0.2.0 (main sidebar not visible), caused by the copied `admin/base.html`.
- The jazzy_tabler integration's `jazzy_tabler/includes/sidebar_bottom.html` loaded the nonexistent `erp_tags` template library, which crashed every admin page unless the project overrode that include.
- A JS error on pages without an active sidebar link.

## [1.7.0] - 2026-10-14
- Swapped the hard admin-theme dependency from `django-jazzmin` to `django-jazzy-tabler>=0.1.1`; `erp_framework.admin.jazzmin_integration` stays available as an opt-in integration (install `django-jazzmin` yourself to use it)
- Dropped unused dependencies: `pytz`, `simplejson`, `dateutils`, `django-compressor`
- Fixed stale reporting test fixtures so the suite runs green for the release workflow (PR #51: report registry namespace, naive datetimes under `USE_TZ=True`, django-slick-reporting 1.4 alignment)
- Refreshed package metadata: `python_requires >= 3.10`, Django 5.2/6.1-era classifiers, corrected project URLs

## [1.6.0] - 2026-09-21
- Fixed MANIFEST.in so the package actually ships erp_framework templates, static files and locale (the v1.5.2 PyPI package shipped none: its manifest still pointed at the retired `ra/` layout)
- Added jazzy_tabler admin integration alongside the existing jazzmin one, and added `ar` locale
- Added system logs and a stats view fix
- Added an option to customize model `__str__` globally or per model
- Enhanced user/report permissions; added autocomplete and report menu icon
- Enabled save_as by default; report start/end dates are now dynamic; fixed CSV export encoding
- Changed report registry namespace (and report URLs) to `<base_model_name>/<report_slug>` (was `<app_label>/<report_slug>`)
- Compatibility with Django 5.2 and django-slick-reporting 1.4.0
- Fixes: IndexError "pop from empty list" on activity changelists, report title, slug generation, duplicated slick-reporting js inclusion, scroll-into-view navigation

## [1.5.2] - 2023-06-07
- Added Jazzmin integration as an option
- Added settings for custom dashboard base template, admin_site_access_permission, report_access_function 
- Simplified creating a widget for a report
- Simplified integrating erp framework with your project
- Align own ReportView to Slick Reporting ReportView
- Removed ReportList View, top_search app, and unused js plugins
- Changed report URL to be app_label/report_lug
- Enhanced demo app and documentation

## [1.5.0] - 2023-05-28
- A makeover and renaming the project to django-erp-framework.


## [1.2.0] - 2020-11-24
- Update slick_reporting to version >= 0.4

## [1.1.1]
# Updated
- Fixed duplicated `jazzmin` in installed apps in the project skeleton

## [1.1.0]
# Updated
- Fixed issues with documentation and project skeleton.

## [1.0.0]
#Added
- Reporting Engine is moved to its own new package [Slick Reporting](https://github.com/ra-systems/django-slick-reporting).   
- Framework no longer depends Postgres Database specifically.
- Update underlying AdminLTE Theme to 3.0.5  


## [v0.1.1] - 2020-01-12
### Added
- Documentation for Ra Settings
- Removal of unneeded css styles, correcting GitHub linguist
- Added setting `RA_DEFAULT_TO_DATETIME` which defaults to start of current year + 1


## [0.0.9] - 2019-12-25
### Added
- Added changelog, docs/faq
- Drop Use of Django Braces
- Support For Django 3
- Upgrade Django to >= 2.2.9


## [0.0.8] - 2019-12-18
### Added
- Activity Tests
- Data generator for tutorial

### Changed
- Enhance documentation and tutorial
- Fix UI around Chart list

### Removed
- Different Legacy Code


## [0.0.7] 2019-12-17
### Added
- Travis CI

### Removed
- `django-compressor` dependency


## [0.0.6] 2019-12-14
### Changed
- Use setup.cfg
- Use Select2 instead of own widget developed for Django 1.11

## [0.0.5] 2019-12-13
### Changed
- Update Tutorial

## [0.0.4] 2019-12-11
### Added
- First release on Github

### Changed
- Upgrade to Python 3 and Django 2.2
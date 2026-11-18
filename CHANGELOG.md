# Changelog
All notable changes to this project are/will be documented in this file.

## [Unreleased]

## [1.7.1]
### Security hardening
- Entity names are HTML-escaped in the admin changelist title and statistics columns (`get_enhanced_obj_title`, `get_stats_icon`), both now built with `format_html`. Thanks to p-w for the fix ([#63](https://github.com/RamezIssac/django-erp-framework/pull/63)).
- Report `_export=csv` and `_export=print` requests now require the report's `export` / `print` permission through `report_access_function`; a denied request gets HTTP 403. Other `_export` actions require `export`.
- Report URLs are wrapped in the admin site's `admin_view`: non-staff users are redirected to the admin login, and a custom `admin_site_access_permission` now applies to reports.
- `admin_site_access_permission` no longer admits every authenticated user when `DEBUG=True`; access requires an active staff user in every mode.
- `EntityAdmin.get_by_slug` requires view or change permission on the model (HTTP 403 otherwise) and looks the object up through `get_queryset(request)`.
- Removed the unused `erp_framework/print_base.html` template.

### Changes
- `description` is now available on every framework admin base (`EntityAdmin`, `TransactionAdmin`, the prepopulated admins and the activity `LogEntryAdmin`) through the new `DescriptionMixin`; each passes it to the changelist context, `None` by default.
- Fixed `erp_framework/js/select2_compat.js` (listed in `EntityAdmin.Media`) missing from the repository, which made admin pages raise "Missing staticfiles manifest entry" (HTTP 500) under `ManifestStaticFilesStorage`.
- `erp_docs` pages now render in a standalone full-page layout (no admin menu/navbar/breadcrumb chrome): a left
  sidebar with only the docs page list (current page highlighted), a slim top bar with the guide title and a
  "Back to the application" link, the same Tabler/Bootstrap 5 assets and theme mode as the jazzy_tabler admin,
  RTL-aware and responsive. Override `erp_docs/base.html` blocks (`title`, `branding`, ...) to brand it.
- When `erp_docs` is installed and `erp_framework.admin.jazzy_tabler_integration` is active, the admin chrome shows
  a "User guide" link (book icon, `ERP_DOCS_TITLE` label, new tab) in the top navbar for users who pass the docs
  access function, through django-jazzy-tabler's `navbar_extra` hook (`jazzy_tabler/includes/navbar_extra.html`);
  disable with `ERP_DOCS_SHOW_ADMIN_LINK = False`. The hook is unreleased: with django-jazzy-tabler 0.2.0 the link is
  absent and nothing breaks. The minimum jazzy-tabler version moves up once the hook is released.
- Fixed the admin layout with django-jazzy-tabler 0.2.0 (main sidebar not visible): the jazzy_tabler integration
  no longer ships a copied `admin/base.html` (a snapshot of the theme's 0.1.1 template taken for the navbar link);
  the theme's own `base.html` is used again.
- Fixed the jazzy_tabler integration's `jazzy_tabler/includes/sidebar_bottom.html` loading the nonexistent
  `erp_tags` template library (it crashed every admin page unless the project overrode that include).
- Added `erp_framework.docs` (label `erp_docs`), an in-app user guide: Markdown pages rendered per request for
  logged-in staff, no build step. Pages are collected from installed apps' `docs/` directories plus
  `ERP_DOCS_SOURCE_DIRS` (later sources shadow earlier ones, so a client project overrides module pages), support YAML
  front-matter (`title`, `order`, `perms` with any-of semantics; no perms = staff-only; denied URLs answer 404), a
  per-language subdirectory, and images/files served through the same gated view. Whole-guide access is pluggable via
  `ERP_DOCS_ACCESS_FUNCTION` (mirrors `report_access_function`). New dependencies: markdown-it-py, mdit-py-plugins, PyYAML.
- Added `erp_framework.admin.prepopulated`: `PrepopulatedInlineMixin` (one inline row per entity, locked sheet,
  read-only entity widget, live computed fields, sticky totals, Enter-as-Tab) and `HeaderLookupAdminMixin`
  (htmx redirect to an existing document when its header is chosen). Ships htmx 2.0.4.
- Prepopulated sheets behave like a spreadsheet: arrow keys move between cells/rows (RTL aware), Enter/Shift+Enter,
  PageUp/PageDown, Ctrl+Up/Down, F2 to edit in a cell, Escape to revert; numeric cells are `inputmode="decimal"`
  text inputs (arrows/wheel never change values); frozen header row and entity column.
- `PrepopulatedInlineMixin.fast_rendering` (default on for locked sheets): lean grid template with rows rendered in
  Python (`erp_grid` tag) — a 526-row journal renders in ~0.3 s / 1.6 MB instead of ~1.1 s / 6.4 MB.
- `PrepopulatedInlineMixin.autosave` + `GridAutosaveAdminMixin`: each row is saved (htmx) when a cell is committed,
  through the admin's own `save_formset`; on the add page the first save creates the document.
- Saving a prepopulated sheet never duplicates rows: a new row whose entity is already saved updates that item.
- Deprecated `PrepopulatedAdmin` / `RaPrePopulatedAdmin` (they override Django's private `_create_formsets`).
- Fixed a JS error on pages without an active sidebar link.
- Requires `django-slick-reporting>=1.5.1`.

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
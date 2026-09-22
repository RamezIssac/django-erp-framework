# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.

## Tests

- Run the suite from the repo root: `python tests/runtests.py --noinput`. Deps: `pip install -e . -r tests/requirements.txt`; `pylibmc` needs system `libmemcached-dev` and `pywatchman` is optional — both can be skipped, this suite never touches memcached/watchman.
- Despite the name, `tests/test_postgres.py` defaults to sqlite (the Postgres block is commented out).
- `runtests.py` escalates `RuntimeWarning` to errors, so under Django >= 5 (default `USE_TZ=True`) naive datetimes in test fixtures are fatal. Suite convention: naive-datetime tests opt out per class/method with `@override_settings(USE_TZ=False)` (see `tests/reporting_tests/test_generator.py`); do not flip `USE_TZ` globally — `test_time_series_columns_inclusion` needs it `True`.
- Report registry/URL namespace is `<base_model_name>/<report_slug>` (commit 717f7ba re-keyed it from app_label; announced in the v1.6.0 CHANGELOG). Test fixtures must reverse/get with the base-model name (`client`, `product`), never `reporting_tests`.
- With django-slick-reporting >= 1.3: list reports (`group_by=None`) must subclass `ListReportView` (plain `ReportView` returns a single empty totals row), and time-series reports must set `date_field` explicitly.

## Release

- Version lives only in `erp_framework/__init__.py` (`setup.cfg` reads it via `attr:`).
- Pushing a `v*` tag runs `.github/workflows/release.yml`: tests, `python -m build`, PyPI publish via OIDC trusted publishing (needs a PyPI trusted publisher for workflow `release.yml` + a GitHub `release` environment), GitHub Release notes from `scripts/extract_changelog.py`, then merges the tag back into `develop`.

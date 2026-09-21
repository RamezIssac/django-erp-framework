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
- `runtests.py` escalates `RuntimeWarning` to errors, so under Django >= 5 (default `USE_TZ=True`) naive datetimes in test fixtures are fatal.
- Known-red on develop as of v1.6.0 (pre-existing, not a regression signal): `reporting_tests` has 19 errors — 16 from stale `reporting_tests.*` registry namespaces (commit 717f7ba re-keyed the registry/URLs from app_label to base-model `model_name`) and 3 from the USE_TZ issue above. `registry_tests` is green.

## Release

- Version lives only in `erp_framework/__init__.py` (`setup.cfg` reads it via `attr:`).
- Pushing a `v*` tag runs `.github/workflows/release.yml`: tests, `python -m build`, PyPI publish via OIDC trusted publishing (needs a PyPI trusted publisher for workflow `release.yml` + a GitHub `release` environment), GitHub Release notes from `scripts/extract_changelog.py`, then merges the tag back into `develop`.

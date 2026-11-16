"""
Discovery, parsing and resolution of the Markdown guide pages.

Sources
-------
Pages live in an ordered list of *source directories*, lowest priority first:

1. the ``docs/`` directory of every installed app that ships one
   (auto-discovery, in ``INSTALLED_APPS`` order, unless
   ``ERP_DOCS_AUTODISCOVER`` is ``False``);
2. every directory listed in ``ERP_DOCS_SOURCE_DIRS``.

When two sources provide a page with the same slug, the one from the *later*
source wins: a client project lists its own guide directory last and shadows
pages shipped by an ERP implementation's modules.

Language
--------
If a source contains a subdirectory named after the active language code
(``ar``, ``en``, ``en-us``...), pages inside it override the same slugs at
the source root for the duration of that language. Language subdirectories
are never exposed as pages themselves.

Front-matter
------------
Pages may start with a YAML block between ``---`` fences::

    ---
    title: Inventory
    order: 10
    perms: ["inventory.view_stockdocument"]
    ---

``title`` (default: first ``#`` heading, else the humanized slug) and
``order`` (default: 100) drive the page list; ``perms`` is a list of Django
permissions with *any-of* semantics: the page is shown to users holding at
least one of them. A page without ``perms`` is visible to any staff user.
"""

import logging
import posixpath
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from django.apps import apps
from django.conf import global_settings
from django.conf import settings as django_settings
from django.utils.translation import get_language

from . import conf

logger = logging.getLogger(__name__)

FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)
HEADING_RE = re.compile(r"^#\s+(?P<title>.+?)\s*$", re.MULTILINE)

DEFAULT_ORDER = 100


@dataclass
class Page:
    """A resolved Markdown page."""

    slug: str  # posix path relative to its root, without the .md suffix
    root: Path  # the root directory it was discovered under (source or language dir)
    path: Path  # absolute path of the .md file
    title: str
    order: int = DEFAULT_ORDER
    perms: list = field(default_factory=list)

    @property
    def directory(self):
        """The slug's directory component ("" for top-level pages)."""
        return posixpath.dirname(self.slug)

    def user_can_view(self, user):
        """Any-of semantics over the declared perms; none => staff-only."""
        if not self.perms:
            return True
        return any(user.has_perm(perm) for perm in self.perms)


def _language_codes():
    """All directory names that should be treated as language subdirs."""
    codes = set()
    for source in (
        getattr(django_settings, "LANGUAGES", None) or global_settings.LANGUAGES,
        global_settings.LANGUAGES,
    ):
        for code, _name in source:
            code = code.lower()
            codes.add(code)
            codes.add(code.split("-")[0])
    return codes


def _language_dir(source):
    """The active language's subdirectory of ``source``, when it exists."""
    language = (get_language() or "").lower()
    if not language:
        return None
    for code in (language, language.split("-")[0]):
        candidate = source / code
        if code and candidate.is_dir():
            return candidate
    return None


def iter_source_dirs():
    """Ordered source directories, lowest priority first, de-duplicated."""
    dirs = []
    if conf.autodiscover_enabled():
        for app_config in apps.get_app_configs():
            candidate = Path(app_config.path) / "docs"
            if candidate.is_dir():
                dirs.append(candidate)
    dirs.extend(Path(directory) for directory in conf.get_source_dirs())
    seen = set()
    for directory in dirs:
        key = str(directory)
        if key not in seen:
            seen.add(key)
            yield directory


def iter_roots():
    """Every scannable root (source + active language dir), lowest priority first."""
    for source in iter_source_dirs():
        yield source
        language_dir = _language_dir(source)
        if language_dir is not None:
            yield language_dir


@lru_cache(maxsize=512)
def _read_text(path_str, mtime_ns):
    return Path(path_str).read_text(encoding="utf-8")


def _parse_page(root, path):
    slug = path.relative_to(root).with_suffix("").as_posix()
    stat = path.stat()
    text = _read_text(str(path), stat.st_mtime_ns)
    meta = {}
    match = FRONT_MATTER_RE.match(text)
    if match:
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            logger.warning("erp_docs: invalid front-matter in %s", path)
            meta = {}
    if not isinstance(meta, dict):
        meta = {}
    title = meta.get("title")
    if not title:
        heading = HEADING_RE.search(text)
        title = heading.group("title") if heading else _humanize_slug(slug)
    perms = meta.get("perms") or []
    if isinstance(perms, str):
        perms = [perms]
    try:
        order = int(meta.get("order", DEFAULT_ORDER))
    except (TypeError, ValueError):
        order = DEFAULT_ORDER
    return Page(
        slug=slug, root=root, path=path, title=str(title), order=order, perms=list(perms)
    )


def _humanize_slug(slug):
    return posixpath.basename(slug).replace("-", " ").replace("_", " ").title()


def scan_root(root):
    """All pages of a single root directory, keyed by slug."""
    root = Path(root)
    pages = {}
    if not root.is_dir():
        return pages
    language_codes = _language_codes()
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        parts = relative.parts
        # Skip hidden/private paths and language subdirectories at the root.
        if any(part.startswith((".", "_")) for part in parts):
            continue
        if root.name not in language_codes and parts[0].lower() in language_codes:
            continue
        page = _parse_page(root, path)
        pages[page.slug] = page
    return pages


def get_pages():
    """The effective pages across all roots; later (higher priority) roots win."""
    pages = {}
    for root in iter_roots():
        pages.update(scan_root(root))
    return pages


def get_page(slug):
    return get_pages().get(slug)


def get_visible_pages(user):
    """Effective pages the user may see, ordered for the page list."""
    pages = [page for page in get_pages().values() if page.user_can_view(user)]
    return sorted(pages, key=lambda page: (page.order, page.slug))


def read_body(page):
    """The page's Markdown body, front-matter stripped."""
    stat = page.path.stat()
    text = _read_text(str(page.path), stat.st_mtime_ns)
    match = FRONT_MATTER_RE.match(text)
    return text[match.end():] if match else text

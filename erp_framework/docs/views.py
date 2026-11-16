import logging
import mimetypes
import posixpath
from pathlib import Path

from django.http import FileResponse, Http404
from django.shortcuts import render
from django.utils._os import safe_join
from django.utils.safestring import mark_safe

from erp_framework.base import app_settings
from erp_framework.sites import erp_admin_site

from . import conf, markdown, pages as pages_module

logger = logging.getLogger(__name__)


def _check_guide_access(request):
    """
    Whole-guide access check (``ERP_DOCS_ACCESS_FUNCTION``).

    Denied requests answer 404 - not 403 - so the existence of the guide (or
    of a single page) is never leaked to users who may not see it.
    """
    if not conf.get_access_function()(request):
        raise Http404


def _base_context(request):
    return {
        **erp_admin_site.each_context(request),
        "docs_title": conf.get_title(),
        "admin_base_site_template": app_settings.get_admin_base_template(
            getattr(request, "current_app", "")
        ),
        "pages": pages_module.get_visible_pages(request.user),
    }


def _render_page(request, page, context=None):
    body = pages_module.read_body(page)
    context = context or _base_context(request)
    context.update(
        {
            "title": page.title,
            "page": page,
            "current_slug": page.slug,
            "content": mark_safe(markdown.render_page(page, body)),
        }
    )
    return render(request, "erp_docs/page.html", context)


def index(request):
    """
    The guide home: renders the ``index`` page when a source provides one,
    otherwise a simple list of the pages the user may see.
    """
    _check_guide_access(request)
    context = _base_context(request)
    context["title"] = conf.get_title()
    index_page = pages_module.get_page("index")
    if index_page is not None and index_page.user_can_view(request.user):
        return _render_page(request, index_page, context)
    return render(request, "erp_docs/index.html", context)


def page(request, page_path):
    """Render a single Markdown page inside the admin chrome."""
    _check_guide_access(request)
    doc_page = pages_module.get_page(page_path.rstrip("/"))
    if doc_page is None or not doc_page.user_can_view(request.user):
        raise Http404
    return _render_page(request, doc_page)


def _find_asset(asset_path):
    """
    Locate ``asset_path`` in the source roots, highest priority first.

    Returns ``(root, absolute_path)`` or None. Path traversal is refused by
    ``safe_join`` (SuspiciousFileOperation -> 400).
    """
    for root in reversed(list(pages_module.iter_roots())):
        candidate = safe_join(str(root), asset_path)
        candidate_path = Path(candidate)
        if candidate_path.is_file():
            return root, candidate_path
    return None


def _asset_perm_pages(root, asset_path):
    """
    The pages governing an asset: pages of the asset's root living in the
    asset's directory, or the nearest ancestor directory that has pages.
    """
    root_pages = pages_module.scan_root(root)
    directory = posixpath.dirname(asset_path)
    while True:
        found = [p for p in root_pages.values() if p.directory == directory]
        if found:
            return found
        if not directory:
            return []
        directory = posixpath.dirname(directory)


def asset(request, asset_path):
    """
    Serve a file (image, ...) stored next to the Markdown sources.

    The asset inherits the permissions of the pages in its directory (or the
    nearest ancestor directory holding pages): it is served only to users
    allowed to view at least one of those pages. Markdown sources themselves
    and hidden/private paths are never served this way.
    """
    _check_guide_access(request)
    parts = asset_path.split("/")
    if (
        asset_path.endswith(".md")
        or any(part.startswith((".", "_")) for part in parts)
    ):
        raise Http404
    found = _find_asset(asset_path)
    if found is None:
        raise Http404
    root, path = found
    perm_pages = _asset_perm_pages(root, asset_path)
    if not perm_pages or not any(p.user_can_view(request.user) for p in perm_pages):
        raise Http404
    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    response = FileResponse(path.open("rb"), content_type=content_type)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

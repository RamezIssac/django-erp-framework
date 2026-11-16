import mimetypes

from django.http import FileResponse, Http404
from django.shortcuts import render
from django.utils.safestring import mark_safe

from erp_framework.base import app_settings
from erp_framework.sites import erp_admin_site

from . import access, markdown, settings
from .pages import find_asset, get_page, read_body


def _base_context(request):
    return {
        **erp_admin_site.each_context(request),
        "docs_title": settings.get_title(),
        "admin_base_site_template": app_settings.get_admin_base_template(
            getattr(request, "current_app", "")
        ),
        "pages": access.get_visible_pages(request.user),
    }


def _render_page(request, page, context=None):
    body = read_body(page)
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
    access.check_guide_access(request)
    context = _base_context(request)
    context["title"] = settings.get_title()
    index_page = get_page("index")
    if index_page is not None and access.user_can_view_page(request.user, index_page):
        return _render_page(request, index_page, context)
    return render(request, "erp_docs/index.html", context)


def page(request, page_path):
    """Render a single Markdown page inside the admin chrome."""
    access.check_guide_access(request)
    doc_page = get_page(page_path.rstrip("/"))
    if doc_page is None or not access.user_can_view_page(request.user, doc_page):
        raise Http404
    return _render_page(request, doc_page)


def asset(request, asset_path):
    """
    Serve a file (image, ...) stored next to the Markdown sources.

    The asset inherits the permissions of the pages in its directory (see
    ``erp_framework.docs.access``); Markdown sources themselves and
    hidden/private paths are never served this way.
    """
    access.check_guide_access(request)
    parts = asset_path.split("/")
    if asset_path.endswith(".md") or any(part.startswith((".", "_")) for part in parts):
        raise Http404
    found = find_asset(asset_path)
    if found is None:
        raise Http404
    root, path = found
    if not access.user_can_access_asset(request.user, root, asset_path):
        raise Http404
    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    response = FileResponse(path.open("rb"), content_type=content_type)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

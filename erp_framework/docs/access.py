"""
Permission logic for the ``erp_docs`` app.

Three layers, all answered with 404 (never 403) so the existence of the
guide, a page, or a file is not leaked:

* whole-guide access (:func:`check_guide_access`) via the pluggable
  ``ERP_DOCS_ACCESS_FUNCTION``;
* per-page visibility (:func:`user_can_view_page`, :func:`get_visible_pages`)
  from the page's front-matter ``perms`` (any-of; absent = staff-only);
* asset gating (:func:`asset_perm_pages`): a file is served only to users
  allowed to view at least one page of its directory (or the nearest
  ancestor directory holding pages).
"""

import posixpath

from django.http import Http404

from . import settings
from .pages import get_pages, scan_root


def user_can_access_guide(request):
    """Whether the request may reach the guide at all."""
    return settings.get_access_function()(request)


def check_guide_access(request):
    """Raise Http404 unless :func:`user_can_access_guide` passes."""
    if not user_can_access_guide(request):
        raise Http404


def user_can_view_page(user, page):
    """Any-of semantics over the page's declared perms; none => staff-only."""
    if not page.perms:
        return True
    return any(user.has_perm(perm) for perm in page.perms)


def get_visible_pages(user):
    """Effective pages the user may see, ordered for the page list."""
    pages = [page for page in get_pages().values() if user_can_view_page(user, page)]
    return sorted(pages, key=lambda page: (page.order, page.slug))


def asset_perm_pages(root, asset_path):
    """
    The pages governing an asset: pages of the asset's root living in the
    asset's directory, or the nearest ancestor directory that has pages.
    """
    root_pages = scan_root(root)
    directory = posixpath.dirname(asset_path)
    while True:
        found = [p for p in root_pages.values() if p.directory == directory]
        if found:
            return found
        if not directory:
            return []
        directory = posixpath.dirname(directory)


def user_can_access_asset(user, root, asset_path):
    """
    Whether ``user`` may download ``asset_path`` from ``root``: allowed when
    the user may view at least one governing page.
    """
    perm_pages = asset_perm_pages(root, asset_path)
    return bool(perm_pages) and any(
        user_can_view_page(user, page) for page in perm_pages
    )

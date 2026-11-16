"""
Markdown rendering for guide pages.

Uses markdown-it-py with the ``default`` preset (tables, strikethrough) plus
``:::`` container admonitions (``note``, ``tip``, ``important``, ``warning``,
``danger``). Raw HTML in pages is escaped, never executed.

Relative URLs are rewritten at render time, against the page being rendered:

* images (and other relative asset links) point at the gated asset view;
* links to sibling ``.md`` pages point at that page's URL.

Traversal (``..`` escaping the source root) leaves the URL untouched, and the
asset view refuses it anyway.
"""

import posixpath
from urllib.parse import urlparse, urlunparse

from django.urls import reverse
from django.utils.html import escape
from markdown_it import MarkdownIt
from mdit_py_plugins.container import container_plugin

ADMONITION_CLASSES = {
    "note": "alert-info",
    "tip": "alert-info",
    "important": "alert-primary",
    "warning": "alert-warning",
    "danger": "alert-danger",
    "caution": "alert-danger",
}


def _admonition_validate(name):
    def validate(params, *args):
        marker = params.strip().split(" ", 1)[0].strip()
        if marker.startswith("{") and marker.endswith("}"):
            marker = marker[1:-1]
        return marker == name

    return validate


def _admonition_render(renderer, tokens, idx, _options, env):
    token = tokens[idx]
    if token.nesting == 1:
        info = token.info.strip()
        marker = info.split(" ", 1)[0].strip()
        name = marker[1:-1] if marker.startswith("{") and marker.endswith("}") else marker
        title = info[len(marker):].strip() or name.capitalize()
        css_class = ADMONITION_CLASSES.get(name, "alert-info")
        return (
            f'<div class="alert {css_class}" role="alert">'
            f'<h4 class="alert-title">{escape(title)}</h4>\n'
        )
    return "</div>\n"


def _is_relative_url(url):
    parsed = urlparse(url)
    return not parsed.scheme and not parsed.netloc and not url.startswith(("#", "/"))


def _resolve_relative(page, reference):
    """Resolve ``reference`` against the page's directory; None on traversal."""
    joined = posixpath.normpath(posixpath.join(page.directory, reference))
    if joined == ".." or joined.startswith("../"):
        return None
    return joined


def build_renderer():
    md = MarkdownIt("default")
    md.options["html"] = False  # never execute raw HTML from pages

    for admonition_name in ADMONITION_CLASSES:
        md.use(
            container_plugin,
            admonition_name,
            validate=_admonition_validate(admonition_name),
            render=_admonition_render,
        )

    default_image_rule = md.renderer.rules["image"]
    render_token = md.renderer.renderToken

    def render_image(tokens, idx, options, env):
        page = env.get("page") if isinstance(env, dict) else None
        token = tokens[idx]
        src = token.attrs.get("src", "")
        if page is not None and _is_relative_url(src):
            parsed = urlparse(src)
            target = _resolve_relative(page, parsed.path)
            if target is not None:
                asset = reverse("erp_docs:asset", kwargs={"asset_path": target})
                token.attrs["src"] = urlunparse(parsed._replace(path=asset))
        return default_image_rule(tokens, idx, options, env)

    def render_link_open(tokens, idx, options, env):
        page = env.get("page") if isinstance(env, dict) else None
        token = tokens[idx]
        href = token.attrs.get("href", "")
        if page is not None and _is_relative_url(href):
            parsed = urlparse(href)
            if parsed.path.endswith(".md"):
                target = _resolve_relative(page, parsed.path[:-3])
                if target is not None:
                    url = reverse("erp_docs:page", kwargs={"page_path": target})
                    token.attrs["href"] = urlunparse(parsed._replace(path=url))
        return render_token(tokens, idx, options, env)

    md.renderer.rules["image"] = render_image
    md.renderer.rules["link_open"] = render_link_open
    return md


_renderer = None


def get_renderer():
    global _renderer
    if _renderer is None:
        _renderer = build_renderer()
    return _renderer


def render_page(page, body):
    """Render a page's Markdown body to (sanitized) HTML."""
    return get_renderer().render(body, {"page": page})

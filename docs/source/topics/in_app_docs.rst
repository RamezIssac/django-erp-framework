In-app user documentation (erp_docs)
-------------------------------------

``erp_framework.docs`` is a contrib app that serves a Markdown user guide
from inside the admin, rendered per request - no build step. Pages live in
plain directories, ship with the code, and can carry per-page permissions.

Setup
=====

Add the app and include its URLconf::

    INSTALLED_APPS = [
        # ...
        "erp_framework.docs",
    ]

    # urls.py
    from django.urls import include, path

    urlpatterns = [
        # ...
        path("docs/", include("erp_framework.docs.urls")),
    ]

Every view is wrapped in ``erp_admin_site.admin_view``, so only logged-in
staff can reach the guide at all.

Where pages come from
=====================

Pages are collected from an ordered list of source directories, lowest
priority first:

1. the ``docs/`` directory of every installed app that ships one
   (auto-discovery, in ``INSTALLED_APPS`` order);
2. the directories listed in ``ERP_DOCS_SOURCE_DIRS``.

When two sources provide a page with the same slug (its path relative to the
source, without ``.md``), the one from the **later** source wins. An ERP
implementation ships a ``docs/`` directory with each module; the client
project lists its own guide directory last and thereby shadows any module
page it wants to customize::

    # settings.py of the client project
    ERP_DOCS_SOURCE_DIRS = [BASE_DIR / "docs" / "guide"]

Language subdirectories
=======================

If a source contains a subdirectory named after the active language code
(``ar``, ``en``...), pages inside it override the same slugs at the source
root for the duration of that language. Untranslated pages fall back to the
source root. Language subdirectories are never listed as pages themselves::

    docs/
        inventory.md        # default language
        ar/
            inventory.md    # served when the active language is Arabic

Authoring pages
===============

Pages are Markdown files; subdirectories are allowed. A page may start with a
YAML front-matter block::

    ---
    title: Inventory
    order: 10
    perms: ["inventory.view_stockdocument"]
    ---

    # Inventory

    How to receive stock...

    ![The stock form](images/receive-form.png)

* ``title``: shown in the page list and breadcrumbs. Default: the first
  ``#`` heading, else the humanized file name.
* ``order``: sort key of the page list (default: 100; ties broken by slug).
* ``perms``: a list of Django permissions with **any-of** semantics - the
  page is visible to users holding at least one of them. A page without
  ``perms`` is visible to any staff user.

The page list on the left shows only pages the current user may see. Opening
a page URL directly without the required permission answers **404** (not
403), so page existence is never leaked.

Markdown support
================

Rendered with `markdown-it-py <https://markdown-it-py.readthedocs.io/>`_:
tables, strikethrough, fenced code, and ``:::`` container admonitions
(``note``, ``tip``, ``important``, ``warning``, ``danger``, ``caution``)::

    :::warning
    Deleting a document cannot be undone.
    :::

Raw HTML in pages is escaped, never executed.

Links to sibling pages (``[Sales](sales.md)``) are rewritten to the page
view; relative image sources are rewritten to the gated asset view.

Images and other files
======================

Reference files relative to the page (``![alt](images/form.png)``) and store
them next to the Markdown sources. They are served through the same view
machinery, so they follow the pages' permissions: a file is served only to
users allowed to view at least one page of its directory (or the nearest
ancestor directory holding pages). Markdown sources, hidden/private paths
(``.``/``_`` prefixes) and path traversal are refused.

Settings
========

``ERP_DOCS_TITLE``
    Guide title shown in the chrome. Default: ``"User guide"``.

``ERP_DOCS_SOURCE_DIRS``
    Extra source directories, appended after the auto-discovered app
    directories. Later entries shadow earlier ones; the client project lists
    its guide last.

``ERP_DOCS_AUTODISCOVER``
    Default ``True``; set to ``False`` to ignore the ``docs/`` directories of
    installed apps and rely on ``ERP_DOCS_SOURCE_DIRS`` only.

``ERP_DOCS_ACCESS_FUNCTION``
    Dotted path to a callable ``(request) -> bool`` controlling access to the
    whole guide (mirrors ``report_access_function``). Default:
    ``erp_framework.docs.helpers.user_can_access_docs`` (any active staff
    member). Denied requests answer 404.

Example
=======

An ERP implementation ships ``inventory/docs/inventory.md`` with its module.
The client project overrides it with its own screenshot and wording::

    # client project: docs/guide/inventory.md  (ERP_DOCS_SOURCE_DIRS lists
    # docs/guide last, so this page wins)
    ---
    title: Inventory
    order: 10
    ---

    # Inventory

    ![Our receive form](images/receive-form.png)

The page keeps its slug (``inventory``) and its place in the page list; only
its content is replaced.

Error tracking (Sentry / GlitchTip)
-----------------------------------

The framework reports server and browser errors to any Sentry-protocol
service (Sentry, GlitchTip) when a DSN is configured. Without a DSN nothing is
loaded or sent.

Setup
=====

Install the optional extra::

    pip install django-erp-framework[sentry]

In ``settings.py``, start the SDK and add the context processor:

.. code-block:: python

    from erp_framework.base.error_tracking import init_sentry

    init_sentry()

    TEMPLATES[0]["OPTIONS"]["context_processors"].append(
        "erp_framework.context_processors.sentry"
    )

Environment variables
=====================

``SENTRY_DSN``
    The project DSN. Empty or unset: error tracking is off.

``SENTRY_ENVIRONMENT``
    The environment name shown in the issue list, e.g. ``test``, ``staging``,
    ``production``.

``SENTRY_RELEASE``
    The deployed version, e.g. ``my-app@<commit sha>``. Events group per release.

Coverage
========

* Server: ``init_sentry()`` starts ``sentry-sdk`` with its Django integration.
* Browser: ``erp_framework/sentry_browser.html`` loads the errors-only Sentry
  browser bundle (pinned version, SRI hash) on every page built on
  ``erp_framework/base_site.html``, on the login page
  (``erp_framework/login.html``, the default ``login_template``) and on the
  in-app docs pages.

Note: list ``erp_framework.admin`` before ``jazzy_tabler`` in ``INSTALLED_APPS``
and not after it, because the theme's own ``admin/base_site.html`` then wins and
the admin pages skip ``erp_framework/base_site.html`` and the snippet.

A project that sets its own ``login_template`` includes the snippet in its
``extrahead`` block:

.. code-block:: django

    {% block extrahead %}
        {{ block.super }}
        {% include "erp_framework/sentry_browser.html" %}
    {% endblock %}

Privacy defaults
================

* ``max_request_body_size="never"``: request bodies (POSTed form data) are not
  sent.
* ``send_default_pii=False`` on the server and ``sendDefaultPii: false`` in the
  browser: cookies, user data (id, username, email) and SQL parameters are not
  sent.
* ``traces_sample_rate=0.0``: errors only, no performance events.
* Frame local variables are off by default.
  ``init_sentry(include_local_variables=True)`` turns them on: stack traces then
  show the values held in each frame, which can include form data and customer
  records.
* The ``django.channels.server`` logger is ignored, the dev server would
  otherwise report every 500 a second time.

Disabling
=========

Unset ``SENTRY_DSN`` (or set it to an empty string) and restart. The
context processor then renders no browser snippet and ``init_sentry()``
returns ``False`` without starting the SDK.

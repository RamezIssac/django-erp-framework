Error tracking (Sentry / GlitchTip)
-----------------------------------

The framework reports server and browser errors to any Sentry-protocol
service (Sentry, GlitchTip) when a DSN is configured. Without a DSN nothing is
loaded or sent.

Setup
=====

sentry-sdk is installed with the framework. Set the DSN in
``ERP_FRAMEWORK_SETTINGS``, typically from the environment:

.. code-block:: python

    ERP_FRAMEWORK_SETTINGS = {
        # ...
        "error_tracking": {
            "dsn": os.getenv("SENTRY_DSN", ""),
            "environment": os.getenv("SENTRY_ENVIRONMENT", ""),
            "release": os.getenv("SENTRY_RELEASE", ""),
        },
    }

``dsn``
    The project DSN. Empty: error tracking is off.

``environment``
    The environment name shown in the issue list, e.g. ``test``, ``staging``,
    ``production``.

``release``
    The deployed version, e.g. ``my-app@<commit sha>``. Events group per release.

``include_local_variables``
    Default ``False``. See the privacy defaults below.

Coverage
========

* Server: ``ERPFrameworkConfig.ready()`` starts ``sentry-sdk`` with its Django
  integration. Errors raised before the apps are loaded (settings import, app
  loading) are not captured.
* Browser: ``erp_framework/sentry_browser.html`` loads the errors-only Sentry
  browser bundle (pinned version, SRI hash) on every page built on
  ``erp_framework/base_site.html``, on the login page
  (``erp_framework/login.html``, the default ``login_template``) and on the
  in-app docs pages. It reads ``error_tracking`` from the admin site's
  ``each_context()``.

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
* Frame local variables are off by default. ``"include_local_variables": True``
  turns them on: stack traces then show the values held in each frame, which
  can include form data and customer records.
* The ``django.channels.server`` logger is ignored, the dev server would
  otherwise report every 500 a second time.

Disabling
=========

Set ``dsn`` to an empty string (or leave ``error_tracking`` out) and restart.
The SDK is then not started and no browser snippet is rendered.

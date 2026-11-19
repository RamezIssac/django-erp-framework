Error tracking
--------------

The framework reports server and browser errors to an error-tracking service
when ``ERP_FRAMEWORK_SETTINGS["error_tracking"]`` names a backend. Without a
backend nothing is loaded or sent.

Setup
=====

Install the backend's SDK (the extras only save typing), then choose the backend
and its options, typically read from the environment:

.. code-block:: bash

    pip install django-erp-framework[sentry]    # or [rollbar], [newrelic], [datadog]

.. code-block:: python

    ERP_FRAMEWORK_SETTINGS = {
        # ...
        "error_tracking": {
            "backend": "sentry",
            "options": {
                "dsn": os.getenv("SENTRY_DSN", ""),
                "environment": os.getenv("SENTRY_ENVIRONMENT", ""),
                "release": os.getenv("SENTRY_RELEASE", ""),
            },
        },
    }

The other backends take the same shape:

.. code-block:: python

    {"backend": "rollbar", "options": {
        "access_token": os.getenv("ROLLBAR_ACCESS_TOKEN", ""),   # server, post_server_item
        "client_token": os.getenv("ROLLBAR_CLIENT_TOKEN", ""),   # browser, post_client_item
        "environment": "production",
        "code_version": os.getenv("GIT_SHA", ""),
    }}

    {"backend": "newrelic", "options": {"browser_timing_header": False}}

    {"backend": "datadog", "options": {
        "application_id": os.getenv("DD_RUM_APPLICATION_ID", ""),
        "client_token": os.getenv("DD_RUM_CLIENT_TOKEN", ""),
        "site": "datadoghq.eu",
        "service": "my-erp", "env": "production", "version": os.getenv("GIT_SHA", ""),
    }}

    {"backend": "myproject.tracking.BugsnagBackend", "options": {...}}

    {"backend": "external", "options": {
        "template": "myproject/error_tracking.html",
        "config": {"api_key": os.getenv("BUGSNAG_KEY", "")},
    }}

An empty DSN or token turns that side off: the server SDK is not started and no
browser snippet is rendered.

How it works
============

* Server: ``ERPFrameworkConfig.ready()`` calls the backend's ``init_server()``.
  Errors raised before the apps are loaded (settings import, app loading) are
  not captured.
* Browser: the admin site's ``each_context()`` asks the backend for its snippet
  template and values. ``erp_framework/error_tracking.html`` renders it on every
  page built on ``erp_framework/base_site.html``, on the login page
  (``erp_framework/login.html``, the default ``login_template``) and on the
  in-app docs pages. Browser SDKs load from a pinned CDN URL with an SRI hash.
* System checks: ``erp_framework.E010`` when the backend's SDK is not installed,
  ``E011`` when ``backend`` cannot be imported, ``E012`` when ``external`` has no
  ``template``, ``W010`` when an agent-driven backend's agent is not running.

Note: list ``erp_framework.admin`` before ``jazzy_tabler`` in ``INSTALLED_APPS``
and not after it, because the theme's own ``admin/base_site.html`` then wins and
the admin pages skip ``erp_framework/base_site.html`` and the snippet.

A project that sets its own ``login_template`` includes the snippet in its
``extrahead`` block:

.. code-block:: django

    {% block extrahead %}
        {{ block.super }}
        {% include "erp_framework/error_tracking.html" %}
    {% endblock %}

Where backends differ
=====================

New Relic and Datadog start before Django
    Their agents instrument the process at start-up, so ``ready()`` is too late
    to start them and the backend starts nothing on the server. Start New Relic
    with ``newrelic-admin run-program`` or ``newrelic.agent.initialize()`` at the
    top of ``wsgi.py`` / ``asgi.py``, configured by ``newrelic.ini`` or
    ``NEW_RELIC_*`` variables. Start Datadog with ``ddtrace-run`` or
    ``import ddtrace.auto`` at the top of ``wsgi.py`` / ``asgi.py``. ``W010``
    reports a process where the agent is not running, e.g. ``manage.py``
    commands; silence it there with ``SILENCED_SYSTEM_CHECKS``.

New Relic browser monitoring
    The agent injects its browser script into HTML responses. Set
    ``browser_timing_header: True`` only when auto-injection is off; the
    framework then renders ``get_browser_timing_header()``.

Rollbar uses two tokens
    ``access_token`` (``post_server_item``) stays on the server.
    ``client_token`` (``post_client_item``) is public and goes to the browser.
    Request exceptions reach Rollbar through Django's ``got_request_exception``
    signal, no middleware entry is needed.

Datadog browser errors come from RUM
    The browser side needs a RUM application: ``application_id`` and
    ``client_token``.

Custom backends
===============

``backend`` accepts a dotted path to a subclass of
``erp_framework.error_tracking.backends.base.ErrorTrackingBackend``. It receives
``options`` and overrides what it needs:

``init_server()``
    Start the server SDK. Called once from ``ready()``.

``browser_config(request)``
    Return the values for ``browser_template`` (rendered with them as
    ``config``), or ``None`` for no snippet.

``check()``
    Return system check messages. The default reports a missing ``sdk_module``.

The built-in ``external`` backend covers a project that starts its tool itself:
the framework does nothing on the server and renders ``options["template"]``
with ``options["config"]``.

Privacy defaults
================

* Sentry: ``send_default_pii=False`` and ``sendDefaultPii: false`` (no cookies,
  user data or SQL parameters), ``max_request_body_size="never"`` (no request
  bodies), ``traces_sample_rate=0.0`` (errors only), the
  ``django.channels.server`` logger ignored (the dev server would otherwise
  report every 500 a second time).
* Rollbar: ``capture_ip=False`` and ``captureIp: false``,
  ``include_request_body=False``.
* Datadog RUM: session replay off, user interactions not tracked,
  ``defaultPrivacyLevel: "mask"``. RUM is not errors only: it records a view
  event for every page and samples every session (``sessionSampleRate: 100``).
* Sentry and Rollbar send frame local variables only with
  ``"include_local_variables": True``. Stack traces then show the values held in
  each frame, which can include form data and customer records.
* New Relic and Datadog APM follow their agent configuration.

Disabling
=========

Remove ``error_tracking`` (or set ``backend`` to an empty value) and restart.

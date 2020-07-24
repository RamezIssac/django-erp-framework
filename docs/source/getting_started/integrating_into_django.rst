.. _integrating_into_django:

Integrating Ra into an existing project
=======================================

First, install the ``django-ra-erp`` package from PyPI:

.. code-block:: console

    $ pip install django-ra-erp

and/or add the package to your existing requirements file.


Settings
--------

* In your settings file, add the following apps to ``INSTALLED_APPS``:

.. code-block:: python

    INSTALLED_APPS = {
        # ...

        'crequest',
        'crispy_forms',
        'reversion',
        'tabular_permissions',
        'ra',
        'ra.admin',
        'ra.activity',
        'ra.reporting',
        'sample_erp',
        'slick_reporting',
        'jazzmin',
        'django.contrib.admin', # comes at the end because the theme is replaced

    }


* Add the following entries to ``MIDDLEWARE``:

.. code-block:: python

        MIDDLEWARE = {
            # ...
            'crequest.middleware.CrequestMiddleware',
        }


* Add the following entries to ``TEMPLATES`` ``context_processors``

.. code-block:: python

    TEMPLATES = {
        'context_processors' = [
            #...
            'django.template.context_processors.i18n',
            'django.template.context_processors.static',
            'ra.base.context_processors.global_info',
        ]
    }


* Add a ``STATIC_ROOT`` setting, if your project does not have one already:

.. code-block:: python

    STATIC_ROOT = os.path.join(BASE_DIR, 'static')


* Add ``MEDIA_ROOT`` and ``MEDIA_URL`` settings, if your project does not have these already:

.. code-block:: python

    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    MEDIA_URL = '/media/'


* Ra uses django-crispy-forms bootstrap 4 for the reporting forms. So we need to add this:

.. code-block:: python

    CRISPY_TEMPLATE_PACK = 'bootstrap4'


* Add default Jazzmin theme Settings

.. code-block:: python

    JAZZMIN_SETTINGS = {
        'navigation_expanded': False,
        "changeform_format": "single",
    }

    JAZZMIN_UI_TWEAKS = {
        "navbar": "navbar-primary navbar-dark",
        "no_navbar_border": True,
        "body_small_text": False,
        "navbar_small_text": False,
        "sidebar_nav_small_text": False,
        "accent": "accent-primary",
        "sidebar": "sidebar-dark-primary",
        "brand_colour": "navbar-primary",
        "brand_small_text": False,
        "sidebar_disable_expand": False,
        "sidebar_nav_child_indent": True,
        "sidebar_nav_compact_style": False,
        "sidebar_nav_legacy_style": False,
        "sidebar_nav_flat_style": False,
        "footer_small_text": False
    }


* Finally, you can add a ``RA_SITE_TITLE`` - which will be displayed on the main dashboard of the Ra dashboard:

.. code-block:: python

    RA_SITE_TITLE = 'My Example Site'


Various other settings are available to configure Ra's behaviour - see :doc:`/advanced_topics/settings`.

URLS configuration
-------------------

We need to hook the dashboard / Ra admin site in ``urls.py``, like so:

.. code-block:: python

    from django.urls import path
    from ra.admin.admin import ra_admin_site

    urlpatterns = [
        # ...
        path('your-url-here', ra_admin_site.urls),
        # ...
    ]



With this configuration in place, you are ready to run ``./manage.py migrate`` to create the database tables used by Ra.

User accounts
-------------

Superuser accounts receive automatic access to the Ra Dashboard interface; use ``./manage.py createsuperuser`` if you don't already have one.

Start developing
----------------

You're now ready to add a new app to your Django project via ``./manage.py startapp``.

Follow to the tutorial to create sample erp system which tracks sales and expense and profitability. :ref:`tutorial_root`


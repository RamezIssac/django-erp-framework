Getting started
===============


Installation
------------

First, install the ``django-erp-framework`` package from PyPI:

.. code-block:: console

    $ pip install django-erp-framework


Usage
-----

* In your settings file, add the following apps to ``INSTALLED_APPS``:

.. code-block:: python

    INSTALLED_APPS = {
        # ...


        'crequest',
        'crispy_forms',
        'crispy_bootstrap4',

        'reversion', # needed only when you add the admin app
        'tabular_permissions',

        'erp_framework',
        'erp_framework.admin',
        'erp_framework.activity',
        'erp_framework.reporting',
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




* Add a ``STATIC_ROOT`` setting, if your project does not have one already:

.. code-block:: python

    STATIC_ROOT = os.path.join(BASE_DIR, 'static')


* Add ``MEDIA_ROOT`` and ``MEDIA_URL`` settings, if your project does not have these already:

.. code-block:: python

    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    MEDIA_URL = '/media/'


* Django-erp-framework uses django-crispy-forms for the reporting forms. So we need to add this:

.. code-block:: python

    CRISPY_TEMPLATE_PACK = 'bootstrap4' # or your version of bootstrap


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


* Finally, you can Change the settings for the django erp framework:

.. code-block:: python


    ERP_FRAMEWORK_SETTING_DEFAULT = {
        "site_name": "ERP Framework System",
        "site_header": "ERP Framework System",
        "index_title": "ERP Framework Dashboard",

        # .. todo
    }


Various other settings are available to configure Django ERP framework's behaviour - see :doc:`/advanced_topics/settings`.

URLS configuration
-------------------

We need to hook the Django ERP admin site in ``urls.py``, like so:

.. code-block:: python

    from django.urls import path
    from erp_framework.admin.admin import erp_admin_site

    urlpatterns = [
        # ...
        path('erp-system/', erp_admin_site.urls),
        # ...
    ]



With this configuration in place, you are ready to run ``./manage.py migrate``

User accounts
-------------

Superuser accounts receive automatic access to the Django ERP framework Dashboard interface; use ``./manage.py createsuperuser`` if you don't already have one.

Start developing
----------------

You're now ready to add a new app to your Django project via ``./manage.py startapp``.

Follow to the tutorial to create sample erp system which tracks sales and expense and profitability. :ref:`tutorial_root`




Running the tests
-----------------

To run the test suite, first, create and activate a virtual environment. Then
clone the repo, install the test requirements and run the tests::

    $ git clone git+git@github.com:RamezIssac/django-erp-framework.git
    $ cd cd django-erp-framework/tests
    $ python -m pip install -e ..
    $ python -m pip install -r requirements/py3.txt
    $ ./runtests.py
    # For Coverage report
    $ coverage run --include=../* runtests.py [-k]
    $ coverage html


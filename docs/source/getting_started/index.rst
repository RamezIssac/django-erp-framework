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


        'crequest', # Need access to the request object in places where request

        'crispy_forms', # For the reports forms,
        'crispy_bootstrap4',

        'reversion', # needed only when you use the admin app
        'tabular_permissions', # better a permission widget , Optional

        'erp_framework',
        "erp_framework.admin.jazzmin_integration", # if you want to use jazzmin theme, otherwise remove this line
        'erp_framework.admin',
        'erp_framework.reporting',
        'slick_reporting',

        'jazzmin', # optional
        'django.contrib.admin', # comes at the end because the theme is replaced
    }


* Add the following entries to ``MIDDLEWARE``:

.. code-block:: python

        MIDDLEWARE = {
            # ...
            'crequest.middleware.CrequestMiddleware',
        }



* Django-erp-framework uses django-crispy-forms for the reporting forms. So we need to add this to our settings.py:

.. code-block:: python

    CRISPY_TEMPLATE_PACK = 'bootstrap4' # or your version of bootstrap


* Add the settings for the django erp framework:

.. code-block:: python


    ERP_FRAMEWORK_SETTING_DEFAULT = {
        "site_name": "ERP Framework System",
        "site_header": "ERP Framework System",
        "index_title": "ERP Framework Dashboard",
    }


Various other settings are available to configure Django ERP framework's behaviour - see :doc:`/advanced_topics/settings`.


URLS configuration
-------------------

We need to hook the Django ERP admin site in ``urls.py``, like so:

.. code-block:: python

    from django.urls import path
    from erp_framework.sites import erp_admin_site

    urlpatterns = [
        # ...
        path('erp-system/', erp_admin_site.urls),
        # ...
    ]



With this configuration in place, you are ready to run ``./manage.py migrate``


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


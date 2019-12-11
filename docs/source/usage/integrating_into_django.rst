.. _integrating_into_django:

Integrating Ra into a Django project
=========================================

Ra provides the ``ra-admin start`` command and project template to get you started with a new Ra project as quickly as possible, but it's easy to integrate Ra into an existing Django project too.

Ra is currently compatible with Django 2.2. First, install the ``django-ra`` package from PyPI:

.. code-block:: console

    $ pip install django-ra

or add the package to your existing requirements file.


Settings
--------

In your settings file, add the following apps to ``INSTALLED_APPS``:

.. code-block:: python

    'crequest',
    'compressor',
    'crispy_forms',
    'reversion',
    'tabular_permissions',
    'ra',
    'ra.admin',
    'ra.activity',
    'ra.reporting',

Add the following entries to ``MIDDLEWARE``:

.. code-block:: python

        'crequest.middleware.CrequestMiddleware',

Add the following entries to ``TEMPLATES`` ``context_processors``

.. code-block:: python

    'django.template.context_processors.i18n',
    'django.template.context_processors.static',
    'ra.base.context_processors.global_info',

Add a ``STATIC_ROOT`` setting, if your project does not have one already:

.. code-block:: python

    STATIC_ROOT = os.path.join(BASE_DIR, 'static')
    
Add ``MEDIA_ROOT`` and ``MEDIA_URL`` settings, if your project does not have these already:

.. code-block:: python

    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    MEDIA_URL = '/media/'

Add a ``RA_SITE_TITLE`` - this will be displayed on the main dashboard of the Ra admin backend:

.. code-block:: python

    RA_SITE_TITLE = 'My Example Site'

Finally, as Ra use Crispy-forms on bootstrap 3, Add

.. code-block:: python

    CRISPY_TEMPLATE_PACK = 'bootstrap3'

Various other settings are available to configure Ra's behaviour - see :doc:`/advanced_topics/settings`.

URL configuration
-----------------

Now make the following additions to your ``urls.py`` file:

.. code-block:: python

    from django.urls import path
    from ra.admin.admin import ra_admin_site

    handler500 = 'ra.utils.views.server_error'
    handler404 = 'ra.utils.views.not_found_error'

    urlpatterns = [
        ...
        path('erp', ra_admin_site.urls),
        ...
    ]


The URL paths here can be altered as necessary to fit your project's URL scheme.

``ra_admin_site.urls`` provides the admin interface for Ra. This is separate from the Django admin interface (``django.contrib.admin``); Ra-only projects typically host the Ra admin at ``/admin/``, but if this would clash with your project's existing admin backend then an alternative path can be used, such as ``/erp/`` here.

With this configuration in place, you are ready to run ``./manage.py migrate`` to create the database tables used by Ra.

User accounts
-------------

Superuser accounts receive automatic access to the Ra admin interface; use ``./manage.py createsuperuser`` if you don't already have one. Custom user models are supported, with some restrictions; Ra uses an extension of Django's permissions framework, so your user model must at minimum inherit from ``AbstractBaseUser`` and ``PermissionsMixin``.

Start developing
----------------

You're now ready to add a new app to your Django project (via ``./manage.py startapp`` - remember to add it to ``INSTALLED_APPS``) and set up models, as described in :doc:`/usage/quickstart`.

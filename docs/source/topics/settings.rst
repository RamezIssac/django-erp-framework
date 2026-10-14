.. _settings:

========
Settings
========

ERP framework settings
======================

.. code-block:: python


        ERP_FRAMEWORK_SETTINGS = {
            "site_name": "ERP Framework System",
            "site_header": "ERP Framework System",
            "index_title": "Dashboard Home",
            "index_template": "admin/index.html",
            "login_template": "admin/login.html",
            "logout_template": "admin/logout.html",
            "app_index_template": "admin/app_index.html",
            # a function to control be dbfield on all instances, Saves you time to subclass if
            # only you need to add a help text or something
            "admin_default_formfield_for_dbfield": (
                "erp_framework.base.helpers.default_formfield_for_dbfield"
            ),
            "admin_site_class": "erp_framework.admin.admin.ERPFrameworkAdminSite",
            "admin_site_namespace": "erp_framework",
            "enable_delete_all": False,
        }




``admin_site_class``
-----------------------

Defaults ``'erp_framework.admin.admin.ERPFrameworkAdminSite'``

A dotted path to the main Django ERP framework Admin Site class.
Make sure to inherit from ``ERPFrameworkAdminSiteBase`` in your custom admin site.


``enable_delete_all``
----------------------

Default ``False``

Control the availability of the admin action "Delete All" on all ERP framework model admin classes.

``admin_default_formfield_for_dbfield``
---------------------------------------

Default to ``'erp_framework.base.helpers.default_formfield_for_dbfield'``

A dotted path a universal hook that gets called on all 'formfield_for_db_field` on the framework.
You can use this hook to universally control the widgets being displayed without needing to manually set it on each RaModelAdmin

The function should have this signature.

.. code-block:: python

    def default_formfield_for_dbfield(model_admin, db_field, form_field, request, **kwargs):
        # do something
        return form_field





Jazzy Tabler settings
=====================

`Jazzy Tabler <https://github.com/RamezIssac/django-jazzy-tabler>`_ is a modern responsive theme for the Django
admin interface, built on Tabler (Bootstrap 5) with light and dark mode. Here is a glimpse of its settings.

To know more head over to the `django-jazzy-tabler package <https://pypi.org/project/django-jazzy-tabler/>`_


``JAZZY_SETTINGS``
.. code-block:: python

    JAZZY_SETTINGS = {
        "site_title": "ERP Framework",
        "site_header": "ERP Framework",
        "site_brand": "ERP Framework System",
        "welcome_sign": "Welcome",
        "navigation_expanded": False,
        "changeform_format": "single",
    }

    JAZZY_UI_TWEAKS = {
        "default_theme_mode": "light",  # "light", "dark" or "auto"
    }

Migrating from django-jazzmin: when ``JAZZY_SETTINGS`` is not defined, jazzy-tabler reads your existing
``JAZZMIN_SETTINGS`` as a fallback, so your current configuration keeps working. ``JAZZY_UI_TWEAKS`` has no
such fallback; its keys are new (e.g. ``default_theme_mode``, ``navbar_fixed``) and the old
``JAZZMIN_UI_TWEAKS`` keys do not apply.



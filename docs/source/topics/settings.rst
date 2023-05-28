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





Jazzmin settings
================

Jazzmin is a modern responsive skin for the Django admin interface based on the excellent AdminLTE project.
Here is a glimpse f its settings.

To know more head over to the `Jazzmin Configuration documentation <https://django-jazzmin.readthedocs.io/configuration/>`_


``JAZZMIN_SETTINGS``
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



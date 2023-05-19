========
Settings
========

Jazzmin settings
================

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





Base Models Settings
====================

See :ref:`base_classes` for information on what are Django ERP framework Base Models and how they interact with the rest of the framework




Flow Control Settings
======================

``RA_ADMIN_SITE_CLASS``
-----------------------

Defaults ``'erp_framework.admin.admin.RaAdminSite'``

A dotted path to the main Django ERP framework Admin Site class.
Make sure to inherit from ``RaAdminSiteBase`` in your custom admin site.

``RA_ENABLE_ADMIN_DELETE_ALL``
------------------------------

Default ``False``

Control the availability of the admin action "Delete All" on all RaModelAdmin.
While users

``ERP_ADMIN_DEFAULT_FORMFIELD_FOR_DBFIELD_FUNC``
---------------------------------

Defaults ``'erp_framework.base.helpers.default_formfield_for_dbfield'``

A dotted path a universal hook that gets called on all 'formfield_for_db_field` on the framework.
You can use this hook to universally control the widgets being displayed without needing to manually set it on each RaModelAdmin

The function should have this signature.

.. code-block:: python

    def default_formfield_for_dbfield(model_admin, db_field, form_field, request, **kwargs):
        ...



``RA_DEFAULT_FROM_DATETIME``
----------------------------

Defaults to start of this year (ie first of January). Type `datetime`


``RA_DEFAULT_TO_DATETIME``
--------------------------

Defaults to start of the next year (ie First of January, current year + 1). Type `datetime`



Customization
=============

``RA_THEME``
------------

Defaults to ``'adminlte'``

If you want to create a new Django ERP framework theme, You can override the templates in another path and set it here .

``ERP_ADMIN_INDEX_TEMPLATE``
---------------------------

Defaults to ``'f'{RA_THEME}/index.html'``


``RA_ADMIN_APP_INDEX_TEMPLATE``
-------------------------------

Defaults to ``'f'{RA_THEME}//app_index.html'``

``RA_ADMIN_LOGIN_TEMPLATE``
---------------------------

Defaults to ``f'{RA_THEME}/login.html'``

``RA_ADMIN_LOGGED_OUT_TEMPLATE``
---------------------------------

Defaults to ``f'{RA_THEME}/logged_out.html'``


``ERP_ADMIN_SITE_TITLE``
-----------------------

Defaults to ``_('Django ERP framework Framework')``

``ERP_ADMIN_SITE_HEADER``
------------------------

Defaults to ``_('Django ERP framework Administration')``


``ERP_ADMIN_INDEX_TITLE``
------------------------

Defaults to  ``_('Statistics and Dashboard')``


Cache
=====

``RA_CACHE_REPORTS``
--------------------
Defaults to ``True``

Enabling Caching for the Reports

``RA_CACHE_REPORTS_PER_USER``
-----------------------------
Defaults to ``True``

Enable Caching the report value not only per its parameters, but also per each user.
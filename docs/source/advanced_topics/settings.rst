========
Settings
========

Ra have a wealth of settings that puts you in control.


Base Models Settings
====================

See :ref:`base_classes` for information on what are Ra Base Models and how they interact with the rest of the framework

``RA_BASEINFO_MODEL``
---------------------

Default: ``'ra.base.models.EntityModel'``

A dotted path to the Base Model from which all other model shall be inherited.


``RA_BASEMOVEMENTINFO_MODEL``
-----------------------------

Default: ``'ra.base.models.BaseMovementInfo'``

A dotted path to the Base Transaction Model from which all other transaction models shall be inherited.


``RA_QUANVALUEMOVEMENTITEM_MODEL``
-----------------------------------

Default: ``'ra.base.models.QuantitativeTransactionItemModel'``

A dotted path to the Base Quantity / Value Transaction Model from which all other transaction models shall be inherited.



Flow Control Settings
======================

``RA_ADMIN_SITE_CLASS``
-----------------------

Defaults ``'ra.admin.admin.RaAdminSite'``

A dotted path to the main Ra Admin Site class.
Make sure to inherit from ``RaAdminSiteBase`` in your custom admin site.

``RA_ENABLE_ADMIN_DELETE_ALL``
------------------------------

Default ``False``

Control the availability of the admin action "Delete All" on all RaModelAdmin.
While users

``RA_FORMFIELD_FOR_DBFIELD_FUNC``
---------------------------------

Defaults ``'ra.base.helpers.default_formfield_for_dbfield'``

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


``RA_NAVIGATION_CLASS``
-----------------------

Defaults to ``'ra.utils.navigation.RaSuitMenu'``

A Dotted path to the navigation render menu.

This class is forked from `Django suit <https://django-suit.readthedocs.io/en/develop/configuration.html#menu>`_


Customization
=============

``RA_THEME``
------------

Defaults to ``'adminlte'``

If you want to create a new Ra theme, You can override the templates in another path and set it here .

``RA_ADMIN_INDEX_TEMPLATE``
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


``RA_ADMIN_SITE_TITLE``
-----------------------

Defaults to ``_('Ra Framework')``

``RA_ADMIN_SITE_HEADER``
------------------------

Defaults to ``_('Ra Administration')``


``RA_ADMIN_INDEX_TITLE``
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
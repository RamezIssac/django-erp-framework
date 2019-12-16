.. _ra_admin:

Ra Site and ModelAdmin
######################


Ra Site
-------
Ra Site is a custom admin site. It provide you the theme and other goodies aimed to make the dashboard more usable.


ModelAdmin Classes
------------------

A subclass of admin.ModelAdmin with various different options

1. whole_changeform_validation
2. `View` page


``RaAdmin`` offer two important hooks to manage little bit complicated flow

1. it offer :fun:py:`RaAdmin.pre_save(self, form, formsets, change)`
   It offers you a hook before saving the whole page to do any management you want. Like saving the total of the invoicelines
   in the Invoice.value field.

2. :func:`whole_changeform_validation(self, request, form, formsets, change, **kwargs)`
   Where you'll get a chance to validate the whole page forms and formsets


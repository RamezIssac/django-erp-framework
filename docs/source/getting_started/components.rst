System Design / Components
==========================


Components
----------

Reporting Engine
~~~~~~~~~~~~~~~~

View , fields , charts

Reporting organization
Reporting permissions



1. **Base Models**
   There are base abstract models which holds attributes and method that the system expect. Those attributes and fields are very generic.
   For reference: :ref:`base_classes`



2. **Admin Site and Models**
   A custom admin site and admin.ModelAdmin subclasses that holds functionality needed for a smooth framework dashboard experience
   For reference: :ref:`erp_admin`


3. **Report Registry and Views** A Registry for reports created. It's also responsible for report menu generation.
   `ReportView` is a subclass of slick_reporting.ReportView with many addition like caching and ajax.


4. **Front End Report/Widget Loader** A collection of Javascript / jQuery function and wrappers to easily create chart/report widgets and take full control on how they are displayed.



Why using the admin?
--------------------

It's much simpler especially around CRUD intensive apps (like ERPs).
* With just one class you can manage all CRUD operations.
* Easily have your url named and reversed
* Multiple Formsets support out of the box.
* It's unified, no need to learn new terminologies. If you worked with the admin you'll know your way around here.
* Admin goodies (list filter, auto form generation, save and continue, save and add new buttons, discovery of related objects that would get deleted)
* Out of the box permissions handling

Now, imagine having to write all of this, again, in class based views.. that's a pain that no one should face.


"But the admin should be for site admins only."

Well, that's an old phrase that gets passed around which i dont find convincing enough.
Maybe it was true in the old days; But now, you dont have to be a `staff` member to be able to log in an admin dashboard.
Also, Django ERP framework dashboard is a custom admin site (independent from your typical admin).


Reporting
---------

Reporting engine itself was moved from this package to be an independent package `Django Slick Reporting <https://github.com/ra-systems/django-slick-reporting>`_

Django ERP framework, apart from the calculation itself, holds functionality of organizing the reports and create html widgets
out of those reports, which can be controlled . and by default support showing results in tables, and different kinds of charts, all in speed.




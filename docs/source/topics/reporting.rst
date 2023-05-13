.. _reporting:

==========
Reporting
==========


As you may have seen in the tutorial Part 2 :ref:`tutorial_2` , you can create a report by creating a subclass of ``ReportView`` class
and register it with the decorator ``@register_report_view``


Let's look at a bare minimum report

.. code-block:: python

    @register_report_view
    class SimpleReport(ReportView):
        base_model = Product
        report_model = SalesLineTransaction
        report_title = 'Simple report'
        columns = ['slug', 'product__name', 'quantity', 'price', 'value']


The model in which this report must be imported during django load. Preferably on AppConfig.ready()

By registering this report, the dashboard have now a new menu item "reports", with a Product sub menu in which you'll find this report FilterForm and results.

Report View
------------

A view class which represent a report with a default structure..

_ document hooks , cache _


Report Form
------------

The report form get generated automatically and you can customize it on several levels.
By default the filter form contains

1. A Date to filter
2. All foreign keys found in the ``report_model`` ,  displayed as a SelectMultiple Widget.
3. In case of a cross tab report, it shows a check "Show the rest".

The report form is responsible for delivering those filters into a queryset filters and hand them to the ReportGenerator

Report JSON Response Structure
-------------------------------

// todo


Javascript
~~~~~~~~~~~


.. _report_loader_api:

Report Loader API
-----------------

Coming soon


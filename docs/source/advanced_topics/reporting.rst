.. _reporting:

==========
Reporting
==========

Know more about the different options to create and customize a report.



Life Cycle
----------

As you may have seen in the tutorials, you can create a report by creating a subclass of ``ReportView`` class
and register it with the decorator ``@register_report_view``

ReportView is basically a subclass of FormView. It receives a GET request and return a JSON result

Let's look at a bare minimum report

.. code-block:: python

    @register_report_view
    class SimpleReport(ReportView):
        base_model = Product
        report_model = SimpleSales
        report_title = 'Simple report'
        form_settings = {}


If you navigate to Reports -> Products, You'll find the new report there, with a form that contains

1. a Date to filter upon
2. All foreign keys in the ``report_model`` ,  displayed as a SelectMultiple Widget.

However you wont find any report table or charts of course.

Let's walk through the different ways of doing so.

Report Form Settings
--------------------

This is the main controller of the report, let's discover possible options.

* group_columns: These are the columns you'd want to display on the report table.
  They have to be either a report_model field, Or, a ``Report Field``

.. code-block:: python

    @register_report_view
    class SimpleReport(ReportView):
        base_model = Product
        report_model = SimpleSales
        report_title = 'Simple report'
        form_settings = {
            'group_columns': ['slug', 'doc_date', 'value']
        }




* group_by: blank or a foreign key name.
  Setting this key will tell the ReportGenerator to "Group By" the records in the report model by the value of
  this field.




Time Series
~~~~~~~~~~~

.. _time_series_pattern:
* Patterns:

* Order


Javascript
~~~~~~~~~~~


.. _report_loader_api:

Report Loader API
-----------------

Coming soon


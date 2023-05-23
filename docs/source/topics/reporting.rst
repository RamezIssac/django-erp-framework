.. _reporting:

==========
Reporting
==========

Reporting is a very important part of any ERP system. It allows you to get a quick overview of your business and to make decisions based on that.
The Reporting engine of the framework was released as a separate package "Django-slick-reporting"

Why? Because it's a very powerful tool that can be used in any Django project, not only in an ERP systems or in a business application.

You can check its docs here : https://django-slick-reporting.readthedocs.io/en/latest/




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



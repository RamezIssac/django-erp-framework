.. _reporting:

==========
Reporting
==========

Reporting is a very important part of any ERP system. It allows you to get a quick overview of your business and to make decisions based on that.
The Reporting engine of the framework was released as a separate package "Django-slick-reporting"

Why? Because it's a very powerful tool that can be used in any Django project, not only in an ERP systems or in a business application.

You can check its docs here : https://django-slick-reporting.readthedocs.io/en/latest/

Here is some quick links:
* How to create time series reports : https://django-slick-reporting.readthedocs.io/en/latest/time_series_options.html
* How to create Cross tab reports : https://django-slick-reporting.readthedocs.io/en/latest/crosstab_options.html


The model in which this report must be imported during django load. Preferably on AppConfig.ready()

By registering this report, the dashboard have now a new menu item "reports", with a Product sub menu in which you'll find this report FilterForm and results.



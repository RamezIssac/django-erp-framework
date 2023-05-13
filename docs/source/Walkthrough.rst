

Walkthrough
=============


Log in to My Shop demo site My Shop https://my-shop.django-erp-framework.com/_ with the following credentials:

username `test`
Password `testuser123`

This is a custom admin site with a dashboard and reporting. :ref:`erp_admin`

You can add this dashboard to your current admin site, or outside of the admin completely <See how>.


In the dashboard You see reports displayed as widgets:

#. Expense total
#. Profitability Monthly
#. Sales list


.. image:: _static/widgets.png
  :width: 800
  :alt: Dashboard
  :align: center


Links
~~~~~

* How to add a widget :ref:`widgets`
* Check the demo index template on github https://github.com/ra-systems/my-shop/blob/main/templates/admin/custom_index.html
* Create a Time Series <link here>

In the left hand side you see the main menu of django apps.
You can see Expense, Sales , and purchase apps.

Expense and Expense Transaction are normal django models and a basic ModelAdmin .

Sales and Purchase are ERP framework models and a ERPModelAdmin. <ERP ModelAdmin link Here>


After you can see the Reports section , you can browse the reports and find the reports you see in the dashboard there.


Apps
----
My Shop is composed of 3 apps to demo django erp framework
Expense, Sales & Purchase

#. Expense:
   is a simple django app with a model Expense and a model ExpenseTransaction. Registered in regular ModelAdmin.

#. Sales: In Sales app we use bundled base model and ModelAdmin

#. Purchase: In Purchase app we can see how to create & customize reports calculations.


.. _adding_charts_widgets:

Adding charts & report widgets
==============================

First let's recap what we did so far

1. we explored the our base models and their respective ModelAdmins
2. we explored how to create several kind reports and how to add multiple charts to a report.

Now let's continue.

Customizing the Home page
-------------------------

Our home page seems little empty, it would be nice if we can have a *report widgets* on it, some tables with relevant data and charts, Yeah ?
Let's display total client sales report table directly into our home.


A Full Report Widget
~~~~~~~~~~~~~~~~~~~~


First let's create a template ``sample_erp/index.html`` template,
then in our settings.py we set this template to be displayed as the index page

.. code-block:: python

    RA_ADMIN_INDEX_PAGE = 'sample_erp/index.html'

And in the our template we add code like this

.. code-block:: django

    {% extends 'erp_framework/base_site.html' %}
    {% load erp_reporting_tags ra_tags %}

    {% block content %}
        <div class="col-sm-12">
            {% get_report base_model='product' report_slug='ProductSalesMonthly' as ProductSalesMonthly %}
            {% get_html_panel ProductSalesMonthly %}
        </div>
    {% endblock %}


Then let's visit our home page, you should see the charts and the report table of the ProductSalesMonthly report.


``get_html_panel`` is a shortcut. Let's add another report without using it to see how it looks

.. code-block:: django

            <div class="col-sm-12">
            {% get_report base_model='client' report_slug='ClientTotalBalance' as client_balances %}
            <h2>{{ client_balances.report_title }}</h2>
            <div data-report-widget
                 data-report-url="{{ client_balances.get_url }}">

                // include this to load a report chart
                <div data-report-chart style="width:100%; height:400px;"></div>

                // include this to load the report table
                <div data-report-table>

                </div>
            </div>

        </div>


The above code loaded the first chart as default. If you want to change the chart to another one available,
just add attribute ``data-report-default-chart="YOUR_CHART_ID"`` to the ``[data-report-chart]`` element



Customizing the View page
-------------------------

Django ERP framework also provide a view page for each EntityModel subclass, registered with `EntityAdmin`.
For example: If you go to the Clients change list page, you'd find a column called "Stats" which will redirect you to a blank page with the title
*Statistics for <Client name>*

Same like what we did with the home page, we can add widgets to be displayed for this specific object.
Let's see how.

First we need a custom template, so lets create `sample_erp/admin/client_view.html`
and assign it to the model admin `view_template`

in `sample_erp/admin.py`

.. code-block:: python

    class ClientAdmin(EntityAdmin):
        ...
        view_template = 'sample_erp/admin/client_view.html'


And in `sample_erp/admin/client_view.html` let's reuse the exact same code we used in the home page, and check the results.

Sure enough, the chart the the table should be displayed, but there is a one problem. The results contains all clients when we are interested in only one.

We can add filters to the report by ``data-extra-params`` to the ``[data-report-widget]``  element with the active client id and other parameters too..

.. code-block:: django

    {% extends 'erp_framework/base_site.html' %}
    {% load erp_reporting_tags %}

    {% block content %}
        {% get_report base_model='client' report_slug='clienttotalbalance' as client_balances %}

        <div data-report-widget
             data-report-url="{{ client_balances.get_url }}"
             data-extra-params="&client_id={{ original.pk }}">

            <div data-report-chart height="50" data-report-default-chart="bar_chart"></div>
            <div data-report-table></div>
        </div>

    {% endblock %}

Reload the page and you should see only the relevant data.

But the chart here is not very helpful, so we can remove it, also a table with only one row can be a little overkill as well, don't you think?

We can further enhance our widget by using the `data-success-callback`
`data-success-callback` take a function name which will be called when server successfully replies with the report data.
This javascript callback must accept two parameters

* response: The json response sent by the server and contains the results of the report (along with other data).
* $elem: the report jquery element *(ie the relevant `$('[data-report-widget]')`)*

Let's see how would that look like

.. code-block:: django

    {% block content %}

    {# Add this line #}
    <h2>Balance is <span class="clientBalance"></span></h2>

    {% get_report base_model='client' report_slug='clienttotalbalance' as client_balances %}
    <div data-report-widget
         data-report-url="{{ client_balances.get_url }}"
         data-extra-params="&client_id={{ original.pk }}"
         data-success-callback="displayBalance">
    </div>
    <div data-report-table></div>
    {% endblock %}


    {% block extra_js %}

        <script>
            function displayBalance(response, $elem) {
                $('.clientBalance').text(response['data'][0]['__balance__']);
            }
        </script>
    {% endblock %}

So what did we do ?

1. we used `data-success-callback="displayBalance"` which should be accessible to the javascript context.
2. we accessed the response sent from the server `data` which is a list of the results, we accessed the first item in that array, and got the `__balance__` property

.. hint::
    The default success callback `$.erp_framework.report_loader.loadComponents` checks for the existence of elements with attr `[data-report-chart]`
    if found it calls `$.erp_framework.report_loader..displayChart`.
    It also check for children elements with attr `[data-report-table]` , if found it calls `$.erp_framework.datatable.buildAdnInitializeDatatable` and pass the response, $elem arguments.


Let's add another report.

.. code-block:: django

    {% get_report base_model='client' report_slug='productclientsales' as client_sales_of_products %}
    <div data-report-widget
         data-report-url="{{ client_sales_of_products.get_url }}"
         data-extra-params="&client_id={{ original.pk }}">

        <div data-report-table></div>
    </div>



Now you should have a good idea on how you can use Django ERP framework framework to build your system.
Tutorial (Part 4) - Adding report widgets on Homepage and View pages
=====================================================================

First let's recap what we did in part 3

1. we explored the concept of time series
2. we explored the concept in crosstab reports

Now let's continue.

Our home page seems little empty, it would be nice if we can have have *report widgets* to it, some tables with relevant data and charts, Yeah ?
Let's display total client sales report table directly into our home.



Customizing the Home page
~~~~~~~~~~~~~~~~~~~~~~~~~~

Table Report Widget
~~~~~~~~~~~~~~~~~~~


First let's create a template ``ra_demo/index.html`` template,
Then in our settings.py we set this template to be displayed as the index page

.. code-block:: python

    RA_ADMIN_INDEX_PAGE = 'ra_demo/index.html
view.html


And in the our template we add code like this

.. code-block:: javascript

    {% extends 'ra/admin/base_site.html' %}
    {% load ra_admin_tags %}

    {% block content %}
        {% get_report base_model='client' report_slug='clienttotalbalance' as client_balances %}
        <div data-report-widget
             data-report-url="{{ client_balances.get_url }}">

            <div data-report-table> </div>
        </div>
    {% endblock %}


Then let's visit our home page..

Here is what we basically did

1. We loaded the report with ``get_report`` providing the `base model` name and the `report slug`.
2. Then we created a div with attrs ``data-report-widget`` which tell Ra javascript that we need to load a report in that section.
3. We provided the url to that report ``data-report-url`` via the ``.get_url`` method of the `ReportView`
4. Finally, we created a child div with attr ``data-report-table`` to load the report in.


Now we can do pretty much the same for Charts.
Let's first create a pie chart for Clients balances report and display that our index page as well.

Remember how to add charts to a report ? Let's revise.

.. code-block:: python

    # in report.py file

    class ClientTotalBalance(ReportView):
        ....
        # add charts settings
        chart_settings = [
        {
            'id': 'balance_pie',
            'title': _('pie'),
            'settings': {
                'chart_type': 'pie',
                'title': _('Clients Balance'),
                'y_sources': ['__balance__'],
                'series_names': [_('Clients Balance')],
            }
        },
    ]

then in our template, we add add a div with `data-report-chart` child to the `[data-report-widget]` div.
like this

.. code-block:: html

        <div data-report-widget
             data-report-url="{{ client_balances.get_url }}">

            <div data-report-chart></div>  <!--  The new line -->
            <div data-report-table></div>
        </div>


You can explore the different attributes supported to
control how the widget is displayed and extra query parameters sent to server :ref:`report_loader_api`.

Now, You can organize your template as you see fit, create bootstrap rows and column, use panels. The world is yours.


Customizing the View page
~~~~~~~~~~~~~~~~~~~~~~~~~
Ra also provide a view page for each BaseInfo subclass, registered with `RaAdmin`.
If you go to the Clients change list page,for example, you'd find a column called "Stats" which will redirect you to a blank page with the title
*Statistics for <Client name>*

Same like what we did with the home page, we can add widgets to be displayed for this specific object.
Let's see how.

First we need a custom template, so lets create `templates/ra_demo/admin/client_view.html`
and assign it to the model admin `view_template`

.. hint::
    Template location can also follow django template finding procedure.

in `ra_demo/admin.py`

.. code-block:: python

    class ClientAdmin(RaAdmin):
        ...
        view_template = 'ra_demo/admin/client_view.html'


And in `templates/ra_demo/admin/client_view.html` let's use the same code we used in the home page, and check the results.

Sure enough, the chart the the table should be displayed, but there is a small problem.

In this page, we're not interested in all the clients data, we're only interested in *one client*.

To add apply this information, we only need to add ``data-extra-params`` to the ``data-report-widget`` html element with the active client id.

.. code-block:: javascript

    {% extends 'ra/admin/base' %}
    {% load ra_admin_tags %}

    {% block content %}
        {% get_report base_model='client' report_slug='clienttotalbalance' as client_balances %}
        <div data-report-widget
             data-report-url="{{ client_sales_of_products.get_url }}"
             data-extra-params="&client_id={{ original.pk }}">

            <div data-report-chart></div>
            <div data-report-table></div>
        </div>
    {% endblock %}

Reload the page and you should see only the relevant data.

But the chart here is not very helpful, so we can remove it.
Also a table with only one row can be a little overkill as well, don't you think?

We can further enhance our widget by using the `data-success-callback`
`data-success-callback` take a function name which will be called when server successfully replies with the report data.
This javascript callback must accept two parameters

* response: The json response sent by teh server and contains the results of the report (along with other data).
* $elem: the report jquery element *(ie the relevant `$('[data-report-widget]')`)*

Let's see how our `client_view.html` would look like now

.. code-block:: javascript

    {% block content %}

    <h2>Balance is <span class="clientBalance"></span></h2>

    {% get_report base_model='client' report_slug='clienttotalbalance' as client_balances %}
    <div data-report-widget
         data-report-url="{{ client_balances.get_url }}"
         data-extra-params="&client_id={{ original.pk }}"
         data-success-callback="displayBalance">

        <div data-report-chart></div>
        <div data-report-table>

    </div>
    {% endblock %}


    {% block extra_js %}
        <script>
            function displayBalance(response, $elem) {
                $('.clientBalance').text(response['data'][0]['__balance__']);
                unblockDiv($elem);
            }
        </script>
    {% endblock %}

So what did we do ?

1. we used `data-success-callback="displayBalance"` *which should be accessible from the javascript context.*
2. we accessed the response sent from the server `data` which is a list of the results, we accessed the first item in that array, and got the `__balance__` property
3. As now control is delegated to our callback, we're in charge to `unblockDiv`, or else the loader will keep on spinning.

.. hint::
    The default success callback `$.ra.report_loader.loadComponents` checks for the existence of elements with attr `[data-report-chart]`
    if found it calls `$.ra.report_loader..displayChart` .
    It also check for children elements with attr `[data-report-table]` , if found it calls `$.ra.datatable.buildAdnInitializeDatatable` and pass the response, $elem arguments.


Before we finish this section, let's bring up the 2 layer report we did before.
Displaying this report here makes perfect sense.

*Remember the report displayed a list of clients (header_report) and choosing a client it opens a popup with the totals of product sales for that client*

This report makes perfect sense to be displayed here on the client view page.

Let's add it.

.. code-block:: html

    {% get_report base_model='client' report_slug='productclientsales' as client_sales_of_products %}
    <div data-report-widget
         data-report-url="{{ client_sales_of_products.get_url }}"
         data-extra-params="&client_id={{ original.pk }}">

        <div data-report-chart></div>
        <div data-report-table></div>
    </div>




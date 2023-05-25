.. _javascript:

Javascript
==========

Document
$.erp_framework


$.erp_framework.report_loader
------------------------------

This is the main function plugin responsible for loading the reports, as widgets or in a standalone report.

You can customize aspects of the loading by passing in options to the function.

.. code-block:: html+django

    <script type="text/javascript">
            $.erp_framework.report_loader.success_callback = function (data, $elem) {
                // data is the ajax response
                // $elem is the element that the report was loaded into, the elem with the ``data-report-widget`` attribute
                // do something
            }
            $.erp_framework.report_loader.fail_callback = function (data, $elem) {
                // data is the ajax response
                // $elem is the element that the report was loaded into, the elem with the ``data-report-widget`` attribute
            }

            $.erp_framework.report_loader.display_chart = function (data, $elem, chart_id) {

                // do something
            }
    </script>


Flow
----

after calling initialize on the page load, the following happens:


search for all elements with the ``data-report-widget`` attribute and
call the report, get the data
Upon getting the data it calls teh success-function-callback which in turn
1. build the table and initialize datatable on it
2. build the chart and initialize the chart

erp_framework.datatable
-----------------------
The plug responsible to build and initialize the datatable on the table element

You can customize it like it

.. code-block:: html+django

    $.erp_framework.datatable.constructTable = function (table_class, columns, column_names, add_footer, total_fields, data){
        // table_class is the class of the table example: table table-striped table-bordered table-hover
        // columns is the list of columns to be displayed
        // column_names is the list of column names to be displayed
        // add_footer is a boolean to add a footer to the table or not
        // total_fields is a list of fields to be totaled
        // data is the data to be displayed in the table, structure is an array of objects, each object represent a row.

        // do something
    }


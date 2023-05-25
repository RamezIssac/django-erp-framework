.. _javascript:

Javascript
==========

.. contents:: Table of Contents
   :local:
   :depth: 2

erp_framework
-------------
This is the main namespace for the framework, it contains all the functions and plugins.

helper functions
----------------
``smartParseFloat``   This is a custom convenience function to handle strings or empty value when numbers are expected (in which case `value` result would be `NaN`.
   If you want to try just replace smartParseFloat with normal `parseFloat` and enter a string or make empty the quantity and/or price field.

``focus_first``

``enable_tab_support``

``parseArabicNumbers``

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

You can customize it like this

.. code-block:: html+django

    $.erp_framework.datatable.defaults = {}
    // a dictionary of default options to be passed to the datatable

    $.erp_framework.datatable.constructTable = function (table_class, columns, column_names, add_footer, total_fields, data){
        // Parameters:
        // table_class is the class of the table example: table table-striped table-bordered table-hover
        // columns is the list of columns to be displayed
        // column_names is the list of column names to be displayed
        // add_footer is a boolean to add a footer to the table or not
        // total_fields is a list of fields to be totaled
        // data is the data to be displayed in the table, structure is an array of objects, each object represent a row.
    }

    $.erp_framework.datatable.buildAndInitializeDataTable = function (data, $elem, extraOptions, successFunction) {
        // Parameters:
        // data is the data to be displayed in the table, structure is an array of objects, each object represent a row.
        // $elem is the element that the report was loaded into, the elem with the ``data-report-widget`` attribute
        // extraOptions is a dictionary of extra options to be passed to the datatable
        // successFunction is a function to be called after the datatable is initialized
    }


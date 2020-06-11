/**
 * Created by ramezashraf on 13/08/16.
 */

(function ($) {
    let _chart_cache = {};

    function failFunction(data, $elem) {
        if (data.status === 403) {
            $elem.hide()
        } else {
            notify_error();
            unblockDiv($elem);
        }
    }

    function loadComponents(data, $elem) {
        let chartElem = $elem.find('[data-report-chart]');
        if (chartElem.length !== 0 && data.chart_settings.length !== 0) {
            displayChart(data, chartElem);
        }
        $.ra.report_loader.createChartsUIfromResponse(data, $elem)
        let tableElem = $elem.find('[data-report-table]');
        if (tableElem.length !== 0) {
            $.ra.datatable.buildAdnInitializeDatatable(data, tableElem);
        }
        // unblockDiv($elem);
    }

    function displayChart(data, $elem, chart_id) {

        // hand over to the chart plugin

        chart_id = chart_id || $elem.attr('data-report-default-chart') || '';
        // if (typeof (chart_id) == 'undefined') {
        //     chart_id = '';
        // }
        // var chart = $elem.find('.reportChart');
        let chart = $elem;
        let chartObject = $.ra.dataComprehension.getObjFromArray(data.chart_settings, 'id', chart_id, true);

        // let chartObject = data.chart_settings[0]
        //chartObject = group_chart_objects[report_slug][chart_id];
        // if (typeof (chartObject) === 'undefined') {
        //     console.log(chart_id + " can't be found in the charts for this report")
        // }
        try {
            let existing_chart = _chart_cache[data.report_slug];
            if (typeof (existing_chart) !== 'undefined') {
                existing_chart.highcharts().destroy()
            }
        } catch (e) {
            console.log(e)

        }

        chartObject = $.ra.highchart.createChartObject(data, chartObject);
        // let chartInst =
        _chart_cache[data.report_slug] = chart.highcharts(chartObject);


        // let chartObject = $.slick_reporting.chartsjs.createChartObject(data,chart_id, {});
        // new Chart($elem, chartObject);

        unblockDiv($elem);
    }

    function refreshReportWidget($elem, no_cache, extra_params) {
        no_cache = no_cache || true;
        // var report_slug = $elem.attr('data-report-slug');
        let successFunctionName = $elem.attr('data-success-callback');
        successFunctionName = successFunctionName || "$.ra.report_loader.loadComponents";
        let failFunctionName = $elem.attr('data-fail-callback');
        failFunctionName = failFunctionName || "$.ra.report_loader.failFunction";
        let url = $elem.attr('data-report-url');
        extra_params = extra_params || ''
        let extraParams = extra_params + ($elem.attr('data-extra-params') || '');

        if (url === '#') return; // there is no actual url, probably not enough permissions
        else url = url + '?';


        // if (no_cache) url = url + '&no-cache' + _getDateFormParams($elem.parents('.panel'));
        if (extraParams !== '') {
            url = url + extraParams;
        }

        $.get(url, function (data) {
            $.ra.cache[data['report_slug']] = jQuery.extend(true, {}, data);
            executeFunctionByName(successFunctionName, window, data, $elem);
        }).fail(function (data) {
            executeFunctionByName(failFunctionName, window, data, $elem);
            // blockDiv($elem);
            //failFunction($elem, data);
        });

    }



    function loadChartWidgets() {
        // Main
        $('[data-report-widget]').each(function (i, elem) {
            var $elem = $(elem);
            refreshReportWidget($elem);
        });
        // $('.chartContainer').on('click', '.groupChartController', function (e) {
        //     $.ra.report_loader.displayChart()
        //     e.preventDefault();
        //     // DisplayChart($(this));
        // });
        // $('.printReportWidget').on('click', function (e) {
        //     e.preventDefault();
        //     var $panel = $(this).parents('.panel');
        //     var url = $panel.find('.chartWidget').attr('data-report-url') + '&print=true';
        //     url = url + _getDateFormParams($panel);
        //     var win = window.open(url, '_blank');
        //     if (win) {
        //         //Browser has allowed it to be opened
        //         win.focus();
        //     }
        // });
        // $('.refreshReportWidget').on('click', function (e) {
        //     e.preventDefault();
        //     refreshReportWidget($(this).parents('.panel').find('.chartWidget'))
        // });

        // attachDatePicker();

    }

    // function getDataFromServer(url, success_function, fail_function) {
    //     $.get(url, success_function).fail(fail_function);
    // }

    function createChartsUIfromResponse(data, $elem, a_class) {
        a_class = typeof a_class == 'undefined' ? 'groupChartController' : a_class;
        let $container = $('<div></div>');

        let chartList = data['chart_settings'];
        let report_slug = data['report_slug'];
        if (chartList.length !== 0) {
            $container.append('<div class="groupChartControllers">' +
                '<ul class="nav nav-charts"></ul></div>');
        }
        var ul = $container.find('ul');
        for (var i = 0; i < chartList.length; i++) {
            var icon;
            var chart = chartList[i];
            if (chart.disabled) continue;
            var chart_type = chart.type;
            if (chart_type === 'pie') icon = '<i class="fas fa-chart-pie"></i>';
            else if (chart_type === 'line') icon = '<i class="fas fa-chart-line"></i>';
            else if (chart_type === 'area') icon = '<i class="fas fa-chart-area"></i>';
            else icon = '<i class="fas fa-chart-bar"></i>';

            ul.append('<li class="nav-link"><a href class="' + a_class + '" data-chart-id="' + chart.id + '" ' +
                'data-report-slug="' + report_slug + '">' + icon + ' ' + capfirst(chart.title) + '</a></li>')
        }
        $elem.prepend($container)
        return $container
    }

    function displayReport(data, url) {
        return
        // Default entry point for report data display
        // Parameters are
        // 1. `data` the json object returned from server which must have keys `report_slug`, `data`, `columns` & `column_names`
        // 2. `url` : Needed mainly for datatables.net flow

        var report_slug = data['report_slug'];

        if (typeof (report_slug) == 'undefined') {
            console.error("Can not proceed: Data returned from server is missing `report_slug` key. " +
                "Present keys are : " + Object.keys(data));
            return;
        }
        var $tabcontent = $('#' + report_slug);
        var table = $tabcontent.find('.report-table');
        var form_settings = data['form_settings'] || {};
        var frontend_settings = form_settings['frontend_settings'] || {};

        // $tabcontent.find('.chartContainer .controls').html($.ra.report_loader.createChartsUIfromResponse(data));
        table.html('');
        $.ra.datatable.destroyAllFixedHeaders();
        $.ra.datatable.buildAdnInitializeDatatable(data, table, {
            datatableContainer: table,
            enableFixedHeader: false,
            ajax_url: url,
            datatableOptions: {css_class: 'display compact'}
        });
        unblockDiv($tabcontent);
        $.ra.cache[report_slug] = data;
        // $tabcontent.find('.groupChartControllers').find('a:first').trigger('click');
    }

    $('body').on('click', '.groupChartController', function (e) {
        e.preventDefault();
        let $this = $(this);
        let data = $.ra.cache[$this.attr('data-report-slug')]
        let chart_id = $this.attr('data-chart-id')
        $.ra.report_loader.displayChart(data, $this.parents('[data-report-widget]').find('[data-report-chart]'), chart_id)

    });

    $.ra.report_loader = {
        cache: $.ra.cache,
        loadChartWidgets: loadChartWidgets,
        refreshReportWidget: refreshReportWidget,
        failFunction: failFunction,
        displayChart: displayChart,
        getDataFromServer: getDataFromServer,
        createChartsUIfromResponse: createChartsUIfromResponse,
        // displayReport: displayReport,
        loadComponents: loadComponents,

    }
})(jQuery);
/**
 * Created by ramez on 11/20/14.
 */
(function ($) {
        var ra_chart_settings = {


            //exporting: {
            //    allowHTML:true,
            //    enabled: faelse,
            //},


            func2: function () {
                var tooltip = '<small>' + this.point.key + '</small><table><tr><td style="color:' + this.series.color +
                    '">' + this.series.name + ': </td> <td style="text-align: right"><b>' +
                    this.point.y + ' </b></td></tr>' +
                    '<tr><td style="color: ' + this.series.color + '">{Percentage}:</td>' +
                    '<td style="text-align: right"><b>' + this.point.percentage + ' %</b></td></tr></table>'
            }
        };

        function normalStackedTooltipFormatter() {

            var tooltip = '<small>' + this.x + '</small><table>' +
                '<tr><td style="color: ' + this.series.color + '">' + this.series.name + ': </td> <td style="text-align: right"><b>' + this.point.y + ' </b></td></tr>' +
                '<tr><td style="color: ' + this.series.color + '">{pertoTotal}:</td><td style="text-align: right"><b>' + this.point.percentage.toFixed(2) + ' %</b></td></tr>' +
                '<tr><td> {Total}:</td><td style="text-align: right"><b>' + this.point.stackTotal + '<b></td></tr>' +
                '</table>';
//style="color: '+ this.series.color+'"
            tooltip = tooltip.format($.ra.defaults.messages);
            return tooltip

        }

        function createChartObject(response, chartOptions) {
            // We create the high chart object in a seperate step for granular control
            // return a high chart settings object ready for consumption
            //if (data.length == 0) return;
            try {


                $.extend(chartOptions, {
                    'sub_title': '',
                });
                // chartOptions = getChartOptions(isGroup, response, chartOptions);
                chartOptions.data = response.data;


                let is_time_series = is_timeseries_support(response, chartOptions); // response.metadata.time_series_pattern || '';
                let reportSeriesNames = response.metadata.time_series_column_names || [];
                let reportSeriesVerboseName = response.metadata.time_series_column_verbose_names || [];

                // var stackedPercentage = chartOptions.stackedPercentage;
                let chart_type = chartOptions.type;

                var enable3d = false;
                let chart_data = {};

                if (is_time_series) {
                    chart_data = get_time_series_data(response, chartOptions)
                } else {
                    chart_data = _getChartData(response, chartOptions)
                }


                let highchart_object = {
                    chart: {
                        type: '',
                        //renderTo: 'container',
                        //printWidth: 600
                    },
                    title: {
                        text: chartOptions.title,
                        // useHTML: Highcharts.hasBidiBug
                        //useHTML: true
                    },
                    subtitle: {
                        text: chartOptions.sub_title,
                        useHTML: Highcharts.hasBidiBug
                        //useHTML: true
                    },
                    yAxis: {
                        // title: {text: chartyAxisTitle},
                        opposite: $.ra.rtl,
                    },
                    xAxis: {
                        // title: {text: chartxAxisTitle},
                        labels: {enabled: true},
                        reversed: $.ra.rtl,
                    },
                    tooltip: {
                        useHTML: Highcharts.hasBidiBug
                    },
                    plotOptions: {},
                    exporting: {
                        allowHTML: true,

                        enabled: true, //!$.ra.rtl,
                        //scale:2,
                    }
                };


                highchart_object.series = chart_data.series;
                if (chart_type === 'bar' || chart_type === 'column' || chart_type === 'pie') {

                    highchart_object.chart.type = chart_type;

                    if (chart_type === 'bar' || chart_type === 'column') {
                        highchart_object['xAxis'] = {
                            categories: chart_data['titles'],
                            // title: {
                            //     text: null
                            // }
                        };
                    }
                    highchart_object['yAxis']['labels'] = {overflow: 'justify'};
                }

                if (chart_type === 'pie') {

                    highchart_object.plotOptions = {
                        pie: {
                            allowPointSelect: true,
                            cursor: 'pointer',
                            dataLabels: {
                                enabled: true,
                                format: '{point.percentage:.1f}% <b>{point.name}</b>',
                            },
                            showInLegend: false, // ($(window).width() >= 1024) ,
                            style: {
                                color: (Highcharts.theme && Highcharts.theme.contrastTextColor) || 'black'
                            }
                        }
                    };

                    highchart_object.tooltip = {
                        useHTML: true,
                        headerFormat: '<small>{point.key}</small><table class="chart-tooltip">',
                        pointFormat: '<tr><td style="color:' + Highcharts.theme.contrastTextColor + '">{series.name}: </td>' +
                            '<td style="text-align: right; color: ' + Highcharts.theme.contrastTextColor + '"><b>{point.y} </b></td></tr>' +

                            '<tr><td style="color: ' + Highcharts.theme.contrastTextColor + '">' + $.ra.highchart.defaults.messages.percent + '</td>' +
                            '<td style="text-align: right; color: ' + Highcharts.theme.contrastTextColor + '"><b>{point.percentage:.1f} %</b></td></tr>',
                        footerFormat: '</table>',
                        valueDecimals: 2
                    };

                    highchart_object['legend'] = {
                        layout: 'vertical',
                        align: 'right',
                        verticalAlign: 'top',
                        x: -40,
                        y: 100,
                        floating: true,
                        borderWidth: 1,

                        shadow: true
                    };

                    if (enable3d) {
                        highchart_object.chart.options3d = {
                            enabled: true,
                            alpha: 45,
                            beta: 0
                        };
                        highchart_object.plotOptions.pie.innerSize = 100;
                        highchart_object.plotOptions.pie.depth = 45;
                    }
                } else if (chart_type === 'column') {
                    if (enable3d) {
                        highchart_object.chart.options3d = {
                            enabled: true,
                            alpha: 10,
                            beta: 25,
                            depth: 50
                        };
                        highchart_object.plotOptions.column = {
                            depth: 25
                        };
                        highchart_object.chart.margin = 70;
                    }
                    if (chartOptions['stacking']) {
                        highchart_object.plotOptions.series = {stacking: chartOptions['stacking']};
                    }
                    if (chartOptions['tooltip_formatter']) {
                        highchart_object.tooltip = {
                            useHTML: true,
                            formatter: chartOptions['tooltip_formatter'],
                            valueDecimals: 2
                        }
                    }
                } else if (chart_type === 'area') {
                    highchart_object.chart.type = 'area';

                    var stacking = 'normal';
                    // if (!enable_percent_stacking) {
                    //     stacking = 'percent';
                    // }
                    highchart_object.plotOptions = {
                        area: {
                            stacking: stacking,
                            marker: {
                                enabled: false
                            }
                        }
                    };
                } else if (chart_type === 'line') {
                    var marker_enabled = true;

                    // disable marker when ticks are more then 12 , relying on the hover of the mouse ;
                    try {
                        if (highchart_object.series[0].data.length > 12) marker_enabled = false;
                    } catch (err) {

                    }

                    highchart_object.plotOptions = {
                        line: {
                            marker: {
                                enabled: false
                            }
                        }
                    };
                    highchart_object.xAxis.labels.enabled = marker_enabled;

                    highchart_object.tooltip.useHTML = true;
                    highchart_object.tooltip.shared = true;
                    highchart_object.tooltip.crosshairs = true;
                }

                if (is_time_series) {
                    highchart_object.xAxis.categories = chart_data.titles;
                    highchart_object.xAxis.tickmarkPlacement = 'on';
                    if (chart_type !== 'line')
                        highchart_object.tooltip.shared = false //Option here;
                } else {
                    highchart_object.xAxis.categories = chart_data.titles
                }

                highchart_object.credits = $.ra.highchart.defaults.credits;
                highchart_object.lang = {
                    noData: $.ra.highchart.defaults.messages.noData
                };
                return highchart_object;
            } catch (err) {
                $.ra.highchart.defaults.notify_error();
                if ($.ra.defaults.debug) {
                    console.log(err);
                }
            }
        }

        // function get_series_column_names(data) {
        //     let names = []
        //     data.columns.forEach(function (item, index) {
        //         names.push(item.verbose_name)
        //     })
        //     return names;
        // }

        function get_time_series_data(response, chartOptions) {
            let data_sources = {};

            let series = []
            chartOptions.data_source.forEach(function (elem, key) {
                data_sources[elem] = []; //{'name': chartOptions.series_name[key],}
                response.columns.forEach(function (col, key) {
                    if (col.computation_field === elem) {
                        data_sources[elem].push(col.name)
                    }
                })
            })
            if (!chartOptions.plot_total) {
                response.data.forEach(function (elem, index) {
                    Object.keys(data_sources).forEach(function (series_cols, index) {
                        let data = []
                        data_sources[series_cols].forEach(function (col, index) {
                            data.push(elem[col])
                        })
                        series.push({
                            'name': elem[chartOptions.title_source],
                            'data': data
                        })

                    })
                })
            } else {
                let all_column_to_be_summed = []
                Object.keys(data_sources).forEach(function (series_cols, index) {
                    all_column_to_be_summed = all_column_to_be_summed + series_cols;
                })
                let totalValues = calculateTotalOnObjectArray(response.data, all_column_to_be_summed)

                Object.keys(data_sources).forEach(function (series_cols, index) {
                    let data = []
                    series_cols.forEach(function (col, index) {
                        data.push(totalValues[col])
                    })
                    series.push({
                        'name': 'Total', //todo
                        'data': data
                    })


                })
            }
            return {
                'categories': response.metadata.time_series_column_verbose_names,
                'titles': response.metadata.time_series_column_verbose_names,
                'series': series,
            }
        }

        function _getChartData(response, chartOptions) {
            let data = response.data;
            let out_title = []
            let out_series = []
            let out_category = []

            // Get data from datatable in the out array parameter for later manipulation
            if (typeof data == 'undefined') {
                var group_datatable = $('#group_report_datatable table').DataTable({retrieve: true});
                data = group_datatable.data();
            }
            out_category = typeof out_category == 'undefined' ? [] : out_category;
            var columns = response.columns;
            // var column_names = chartOptions.column_names;
            let totalsOnly = chartOptions.plot_total;

            // var report_series = chartOptions.reportSeries;
            var matrix_core_columns = chartOptions.matrixSeries;
//    datatable = typeof datatable != 'undefined' ? datatable : group_datatable;

            var y_sources = chartOptions.data_source;
            var selected_y_sources = chartOptions.selected_y_sources;
            var chart_type = chartOptions.chartType;
            var for_pie = chart_type === 'pie';

            var title_col = chartOptions.title_source; //Happens only when there is a group by doc_type , the table would have no columns containing title , which will error
            var chart_data = [];
            var data_array = [];
            // var matrix_data_array = [];
            var provide_matrix_support = is_matrix_support(matrix_core_columns, true, chartOptions);
            let provide_time_series_support = is_timeseries_support(response, chartOptions);

            let matrix_column_names = false; //todo
            if (provide_time_series_support) {

            }
            // if (matrix_core_columns != null) {
            //     //Get Column Names
            //     var matrix_column_names = $.map(matrix_core_columns, function (element, i) {
            //         var col_name;
            //         for (var t = 0; t < columns.length; t++) {
            //             z = columns[t].indexOf(element);
            //             if (z > -1) {
            //                 col_name = column_names[t];
            //                 break;
            //             }
            //         }
            //         return col_name;
            //     });
            //     $.each(matrix_core_columns, function () {
            //         matrix_data_array.push({})
            //     })
            // }
            if (data.length > 400) {
                return []; //not enough pixels for each entry , 400 can be changed to fit number of rows
            }
            // columns.forEach(function(item, index){
            //     if (item.name.indexOf('title') > -1){
            //         title_col = item.name
            //     }
            //     if (item.name.indexOf('doc_date') > -1) {
            //         var date_col = columns[i];
            //     }
            //     // if (~columns[i].indexOf('balance')) {
            //     //     total_col = columns[i];
            //     // }
            // })
            // if (date_col != null) title_col = date_col;


            if (totalsOnly && provide_time_series_support) {
                // case of time series , want to plot on total values of selected y_sources
                // var series_col_names = $.map(reportSeriesNames, function (element, i) {
                //     return y_sources[0].slice(0, -1) + '_TS' + element
                // });
                // out_title = $.map(report_series, function (element, i) {
                //     return element;
                // });

                let series_col_names = reportSeriesNames;
                out_title = reportSeriesVerboseName;

                var totalValues = calculateTotalOnObjectArray(data, series_col_names);
                var series_data_array;
                if (chart_type === 'pie') {
                    series_data_array = $.map(series_col_names, function (element, i) {
                        return {
                            name: chartOptions['reportSeriesNames'][i],
                            y: $.ra.smartParseFloat(totalValues[element])
                        };
                    });


                } else {
                    series_data_array = $.map(series_col_names, function (element, i) {
                        return $.ra.smartParseFloat(totalValues[element]);
                    });

                }
                out_series.push(
                    {
                        name: selected_y_sources[0],
                        data: series_data_array
                    }
                );

                return chart_data;

            } else if ((totalsOnly && provide_matrix_support) //case of matrix Col
                || matrix_column_names != null && chart_type === 'pie') { // Automatic switch to total , for now #todo allow for multi simultious pie chart
                series_col_names = $.map(matrix_core_columns, function (element, i) {
                    return y_sources[0].slice(0, -1) + 'MX' + element
                });
//        out_title = $.map(matrix_column_names,function(element,i){
//            return 'أجمالي  ' + element;
//        });
                $.each(matrix_column_names, function (i, val) {
                    out_title.push('أجمالي  ' + val);
                });
                $.each(matrix_column_names, function (i, val) {
                    out_category.push(val);
                });
//        out_category = matrix_column_names;

                totalValues = calculateTotalOnObjectArray(data, series_col_names);
                series_data_array = $.map(series_col_names, function (element, i) {
//            return totalValues[element];
                    if (typeof (totalValues[element]) != 'undefined')
                        return smartParseFloat(totalValues[element]);
                    else
                        return 0;
                });
                if (!for_pie) {
                    out_series.push(
                        {
                            name: selected_y_sources[0],
                            data: series_data_array
                        }
                    );
                } else {
                    var pie_data = adjustDataForPie(out_category, series_data_array);
                    out_series.push({
                        name: 'إجمالي  ' + selected_y_sources[0],
                        data: pie_data
                    });
                }


                return chart_data;

            } else {
                // Normal Loop through the values to get the chart series
                for (i = 0; i < data.length; i++) {
                    var title_text = data[i][title_col];
                    // title_text = $(title_text).text() || title_text;

                    if (!provide_matrix_support) {
                        out_title.push(title_text);
                    } else {
                        out_category.push(title_text)
                    }

                    for (var z = 0; z < y_sources.length; z++) {
                        if (!(provide_time_series_support || provide_matrix_support)) {
                            if (typeof data_array[z] == 'undefined') {
                                data_array[z] = [];
                            }
                            var _value = data[i][y_sources[z]];
                            if (typeof (_value) == 'string') {
                                try {
                                    _value = _value.replace(/,/g, '');
                                } catch (err) {
                                    console.log(err, _value, typeof (_value));
                                }
                            }
                            data_array[z].push(parseFloat(_value));

                        } else if (provide_matrix_support) {
                            //case of matrix series ;
                            // data are retrived form teh server with the datatable structure
                            // and saved in report_series .. a list of dates like '20141230'
                            for (var s = 0; s < matrix_core_columns.length; s++) {
                                if (typeof data_array[s] == 'undefined') {
                                    data_array[s] = [];
                                }


                                var series_field_name = y_sources[0].slice(0, -1);
                                series_field_name = series_field_name + 'MX' + matrix_core_columns[s];
                                _value = data[i][series_field_name];
                                if (typeof (_value) == 'string') {
                                    try {
                                        _value = _value.replace(/,/g, '');
                                    } catch (err) {
                                        console.log(err, _value, typeof (_value));
                                    }
                                }

                                data_array[s].push(parseFloat(_value));


                            }

                        } else {
                            //case of time series ;
                            // data are retrived form teh server with the datatable structure
                            // and saved in report_series .. a list of dates like '20141230'


                            if (typeof data_array[i] == 'undefined') {
                                data_array[i] = [];
                            }
                            for (var s = 0; s < report_series.length; s++) {

                                var series_field_name = y_sources[0].slice(0, -1);
                                series_field_name = series_field_name + '_TS' + report_series[s];
                                _value = data[i][series_field_name];
                                if (typeof (_value) == 'string') {
                                    try {
                                        _value = _value.replace(/,/g, '');
                                    } catch (err) {
                                        console.log(err, _value, typeof (_value));
                                    }
                                }
                                _value = smartParseFloat(_value);
                                data_array[i].push(_value);

                            }
                        }
                    }
                }
            }
            var series = [];
            //console.log('data_array' , data_array ) ;
            if (for_pie == true) {

                var pie_position = 300;
                for (var main_array = 0; main_array < data_array.length; main_array++) {
                    _data = [];
                    for (var sub_array = 0; sub_array < data_array[main_array].length; sub_array++) {

                        _data.push({
                            name: out_title[sub_array],
                            y: parseFloat(data_array[main_array][sub_array])
                        });
                    }
                    //console.log('pushing') ;
                    //console.log('_data' , _data) ;

                    var serie_object = {
                        type: 'pie',
                        name: selected_y_sources[main_array],
                        data: _data

                    };
                    if (data_array.length > 1) {
                        //#todo compute to make it look good
                        serie_object.center = [pie_position, 150];
                        serie_object.size = 200

                    }
                    out_series.push(serie_object);

                    pie_position = pie_position + 550;
                    //console.log(out_series) ;
                }

            } else {
                if (provide_time_series_support == false && provide_matrix_support == false) {
                    for (i = 0; i < selected_y_sources.length; i++) {


                        out_series.push(
                            {
                                name: selected_y_sources[i],
                                data: data_array[i]
                            }
                        );
                    }
                } else if (provide_matrix_support) {
                    for (i = 0; i < data_array.length; i++) {
                        out_series.push(
                            {
                                name: matrix_column_names[i],
                                data: data_array[i]
                            }
                        );
                    }

                } else {
                    for (i = 0; i < data_array.length; i++) {
                        out_series.push(
                            {
                                name: out_title[i],
                                data: data_array[i]
                            }
                        );
                    }

                }
            }


            //console.log('out_series',out_series);
            if (out_category.length > 0) {
                out_title = out_category;
            }
            return {'titles': out_title, 'series': out_series, 'category': out_category};
        }


        function adjustDataForPie(names, series_data_array) {
            return $.map(series_data_array, function (element, i) {
                return {name: names[i], y: element}
            });
        }


        function is_matrix_support(matrix_series, isGroup, chartOptions) {
            if (matrix_series == null) {
                return false;
            } else {
                if (chartOptions['matrix_scope'] == 'both') return true;
                else if (isGroup && chartOptions['matrix_scope'] == 'group') {
                    return true;
                } else return !!(isGroup == false && chartOptions['matrix_scope'] == 'details');
            }
        }


        function is_timeseries_support(response, chartOptions) {
            return response.metadata.time_series_pattern || ''
            // return (timeseries_columns != null && !chartOptions.no_time_series_support);
        }


        function shouldDisplayChart(chartObject) {
            //This function checks the chartObject for empty , Nan series
            // and return a visibility check = false if no chart would be drawed

            var series_data = chartObject.series[0].data;
            if (series_data.length == 1) {
                return false;
            } else {
                return true;
            }
        }


        function checkChartSeries(series) {
            for (var i = 0; i < series.length; i++) {
                if (isNaN(series[i])) {
                    series.splice(i, 1)
                }
            }
            return series;
        }


        $.ra.highchart = {
            createChartObject: createChartObject,
            defaults: {
                normalStackedTooltipFormatter: normalStackedTooltipFormatter,
                messages: {
                    noData: 'No Data to display ... :-/',
                    total: 'Total',
                    percent: 'Percent',
                },
                credits: {
                    text: 'RaSystems.io',
                    href: 'https://rasystems.io'
                },
                notify_error: notify_error,
                enable3d: false,

            }
        };

    }

    (jQuery)
);
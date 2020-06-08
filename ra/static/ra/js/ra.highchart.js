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

        function transform_to_pie(chartObject_series, index, categories) {
            index = index || 0;
            let new_series_data = []
            chartObject_series.forEach(function (elem, key) {
                new_series_data.push({
                    'name': elem.name,
                    'y': elem.data[index]
                })
            })
            return {
                'name': categories[index],
                'data': new_series_data
            }
        }

        function createChartObject(response, chartOptions) {
            // Create the chart Object
            // First specifying the global default
            // second, Get the data from the serponse
            // Adjust the Chart Object accordingly

            try {


                $.extend(chartOptions, {
                    'sub_title': '',
                });
                // chartOptions = getChartOptions(isGroup, response, chartOptions);
                chartOptions.data = response.data;


                let is_time_series = is_timeseries_support(response, chartOptions); // response.metadata.time_series_pattern || '';
                let chart_type = chartOptions.type;
                var enable3d = false;
                let chart_data = {};

                if (is_time_series) {
                    chart_data = get_time_series_data(response, chartOptions)
                } else {
                    chart_data = get_normal_data(response, chartOptions)
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
                    highchart_object.series = [transform_to_pie(chart_data.series, 0, chart_data.categories)]
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

                    // highchart_object.tooltip = {
                    //     useHTML: true,
                    //     headerFormat: '<small>{point.key}</small><table class="chart-tooltip">',
                    //     pointFormat: '<tr><td style="color:' + Highcharts.theme.contrastTextColor + '">{series.name}: </td>' +
                    //         '<td style="text-align: right; color: ' + Highcharts.theme.contrastTextColor + '"><b>{point.y} </b></td></tr>' +
                    //
                    //         '<tr><td style="color: ' + Highcharts.theme.contrastTextColor + '">' + $.ra.highchart.defaults.messages.percent + '</td>' +
                    //         '<td style="text-align: right; color: ' + Highcharts.theme.contrastTextColor + '"><b>{point.percentage:.1f} %</b></td></tr>',
                    //     footerFormat: '</table>',
                    //     valueDecimals: 2
                    // };

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

        function get_normal_data(response, chartOptions) {
            let data_sources = {};
            let series = []
            chartOptions.data_source;
            let categories = []
            chartOptions.data_source.forEach(function (elem, key) {
                data_sources[elem] = []; //{'name': chartOptions.series_name[key],}
                response.columns.forEach(function (col, key) {
                    if (elem === col.name) {
                        data_sources[elem].push(col.name)
                        categories.push(col.verbose_name)
                    }
                })
            })

            response.data.forEach(function (elem, index) {
                series.push({
                    'name': elem[chartOptions.title_source],
                    'data': [elem[chartOptions.data_source]]
                })
            })
            return {
                'categories': categories,
                'titles': categories,
                'series': series,
            }
        }

        function get_time_series_data(response, chartOptions) {

            let series = []
            let data_sources = {};
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
                // 'categories': response.metadata.time_series_column_verbose_names,
                'titles': response.metadata.time_series_column_verbose_names,
                'series': series,
            }
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
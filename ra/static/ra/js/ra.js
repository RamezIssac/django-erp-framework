/**
 * Created by ramez on 1/5/15.
 */



function parseArabicNumbers(str) {
    str = typeof str == 'undefined' ? '0' : str;
    return Number(str.replace(/[٠١٢٣٤٥٦٧٨٩]/g, function (d) {
        return d.charCodeAt(0) - 1632;
    }).replace(/[۰۱۲۳۴۵۶۷۸۹]/g, function (d) {
        return d.charCodeAt(0) - 1776;
    }));
}

function calculateTotalOnObjectArray(data, columns) {
    // Compute totals in array of objects
    // example :
    // calculateTotalOnObjectArray ([{ value1:500, value2: 70} , {value:200, value2:15} ], ['value'])
    // return {'value1': 700, value2:85}

    let total_container = {};
    for (let r = 0; r < data.length; r++) {

        for (let i = 0; i < columns.length; i++) {
            if (typeof total_container[columns[i]] == 'undefined') {
                total_container[columns[i]] = 0;
            }
            let val = data[r][columns[i]];
            if (val === '-') val = 0;

            else if (typeof (val) == 'string') {
                try {
                    val = val.replace(/,/g, '');
                } catch (err) {
                    console.log(err, val, typeof (val));
                }
            }
            total_container[columns[i]] += parseFloat(val);
        }
    }
    return total_container;
}

function notify_message(message, type, timeout) {
    if (typeof message == 'object') {
        return new Noty(message).show();

    } else {
        timeout = typeof timeout == 'undefined' ? 3000 : timeout;

        let obj = {
            text: message,
            type: type,
            dismissQueue: false,
            layout: $.ra.rtl ? 'topLeft' : 'topRight',
            killer: true,
            theme: 'relax',
            timeout: timeout,
            //animation: {
            //    open: 'animated lightSpeedIn',
            //    close: 'animated lightSpeedOut',
            //    easing: 'swing',
            //    speed: 100 // opening & closing animation speed
            //},

        };
        return new Noty(obj).show();
    }

}


function notify_success(m, timeout, killer) {
    timeout = timeout || 1500;
    killer = killer || true;
    m = typeof m == 'undefined' ? $.ra.defaults.messages.SuccessMessage : m;
    m = '<i class=" icon-checkmark-circle"> </i> ' + m;
    notify_message(m, 'success', timeout);
}

function notify_error(message, timeout) {
    timeout = typeof timeout == 'undefined' ? 4000 : timeout;
    message = typeof message == 'undefined' ? $.ra.defaults.messages.ErrorMessage : message;
    if (typeof message == 'object') {
        $.each(message, function (i, e) {
            let html = $('<ul>');
            let li = $('<li>');
            li.text(i + ': ' + e);
            html.append(li);
            notify_message({text: html.text(), type: 'error', timeout: timeout, killer: true});
        });
        return;
    }
    notify_message({text: message, type: 'error', timeout: timeout, killer: true});

}


function blockDiv(div) {
    div = typeof div == 'undefined' ? $(window) : div;
    div.block({
        overlayCSS: {
            backgroundColor: '#fff'
        },
        message: '<img src="/static/ra/images/loading.gif" />  ' + $.ra.defaults.messages.WaitMessage,
        css: {
            border: 'none',
            color: '#333',
            background: 'none'
        }
    });
}

function blockInput($input) {
    $input = typeof $input == 'undefined' ? $('.main-content') : $input;
    $input.block({
        overlayCSS: {
            backgroundColor: '#fff'
        },
        message: '<img src="/static/ra/images/loading.gif" /> ',
        css: {
            border: 'none',
            color: '#333',
            background: 'none'
        }
    });
}

function unblockDiv(div) {
    div = typeof div == 'undefined' ? $(window) : div;

    div.unblock();
}


function executeFunctionByName(functionName, context /*, args */) {
    let args = Array.prototype.slice.call(arguments, 2);
    let namespaces = functionName.split(".");
    let func = namespaces.pop();
    for (let i = 0; i < namespaces.length; i++) {
        context = context[namespaces[i]];
    }
    try {
        func = context[func];

    } catch (err) {
        console.error('Function {0} is not found the context {1}'.format(functionName, context), err)
    }
    return func.apply(context, args);
}


function capfirst(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
}


(function ($) {


    $.ra = function (options) {
        let opts = $.extend({}, $.ra.defaults, options);

        function enable_tab_support() {
            //support for enter key as a navigation
            let focusables = $(':focusable');
            $('input').not('[ra_autocomplete_bind="true"]').not('[type="search"]').not('#top_search_box')
                .on("keydown", function (event) {
                    if (event.keyCode == 13) {
                        let current = focusables.index(this);
                        let check = false;
                        while (check == false) {
                            let next = getNext(current);
                            let readOnly = $(next).attr('readonly');

                            if (typeof readOnly == 'undefined') {
                                check = true;
                            }
                            if ($(next).hasClass('delete-row')) {
                                check = false;
                            }
                            current++;
                        }
                        next.focus();
                        next.select();
                        event.preventDefault();
                    }

                    function getNext(current) {
                        return focusables.eq(current + 1).length ? focusables.eq(current + 1) : focusables.eq(0);
                    }
                });
        }

        function smartParseFloat(number, to_fixed) {
            // Wrapper around parseFloat aimed to deliver only numbers

            let val = parseFloat(number);
            if (isNaN(val)) return 0;
            else {
                if (to_fixed > 0 && to_fixed <= 20) return val.toFixed(to_fixed);
                else return val
            }

        }


        return {
            enterTabSupport: enable_tab_support,

        }
    };

    $.ra.defaults = {
        debug: true,

        messages: {
            RedirectionMessage: 'Redirecting...',
            DoneMessage: "Done...",
            SuccessMessage: "<i class='icon-checkmark-circle'></i> Done...",
            ErrorMessage: "An error happened :( ",
            WaitMessage: 'Just a moment...',
            LoadingMessage: 'loading...',
            slug_verbose: 'slug',
            title_verbose: 'title',
            choose: 'choose',
            choice: 'choice',
            to_code: 'to code',
            from_code: 'from code',
            select_all: 'Select All',
            select_none: 'Select None',
            inverse: 'Inverse',
            apply: 'Apply',
            choiceBeenMade: 'Choice made',
            total: 'total',
            availableReports: 'available reports',
            availableCharts: 'available charts',
        },
        urls: {
            settings_portal: '/backend/settings/update/',
        },
    };

    $.ra.cache = {};
    $.ra.rtl = false;

    $.ra.debug = false; // turned on only on dev ;
}(jQuery));

        

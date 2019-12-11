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

    var total_container = {};
    for (var r = 0; r < data.length; r++) {

        for (var i = 0; i < columns.length; i++) {

            if (typeof total_container[columns[i]] == 'undefined') {
                //console.log('columns i ', columns[i]);
                total_container[columns[i]] = 0;
            }
            var val = data[r][columns[i]];
            if (val == '-') val = 0;

            else if (typeof(val) == 'string') {
                try {
                    val = val.replace(/,/g, '');
                }
                catch (err) {
                    console.log(err, val, typeof(val));
                }
            }
            total_container[columns[i]] += parseFloat(val);
//            {#            console.log(val,parseFloat(val),total_container[columns[i]] )#}
        }
    }
    return total_container;
}

function notify_message(message, type, timeout) {
    if (typeof message == 'object') {
        return new Noty(message).show();

    }
    else {
        timeout = typeof timeout == 'undefined' ? 3000 : timeout;

        var obj = {
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


function partialStringInArray(array, string) {
    var found = false;
    $.each(array, function (i, val) {

        if (string.indexOf(val.slice(0, -1)) > -1) {
            found = true;
//                    console.log('found ' , val,string );
            found = val;
//            return val;
        }

    });
    return found;
}


function numberWithCommas(x) {
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
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
            var html = $('<ul>');
            var li = $('<li>');
            li.text(i + ': ' + e);
            html.append(li);
            notify_message({text: html.text(), type: 'error', timeout: timeout, killer: true});
        });
        return;
    }
    notify_message({text: message, type: 'error', timeout: timeout, killer: true});

//    $.gritter.add({
//                // (string | mandatory) the heading of the notification
//                title: $.fn.ra_client.defaults.ErrorMessage,
//                // (string | mandatory) the text inside the notification
//                text: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus eget tincidunt velit. Cum sociis natoque penatibus et <a href="#" style="color:#ccc">magnis dis parturient</a> montes, nascetur ridiculus mus.',
//                // (string | optional) the image to display on the left
//                image: 'assets/images/avatar-1.jpg',
//                // (bool | optional) if you want it to fade out on its own or just sit there
//                sticky: false,
//                // (int | optional) the time you want it to be alive for before fading out
//                time: '',
//                // (string | optional) the class name you want to apply to that specific message
//                class_name: 'my-sticky-class'
//            });

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
    var args = Array.prototype.slice.call(arguments, 2);
    var namespaces = functionName.split(".");
    var func = namespaces.pop();
    for (var i = 0; i < namespaces.length; i++) {
        context = context[namespaces[i]];
    }
    try {
        func = context[func];

    } catch (err) {
        console.error('Function {0} is not found the context {1}'.format(functionName, context), err)
    }
    return func.apply(context, args);
}

function getFunctionByPath(path) {
    // return the function (don't invoke it)
    path = path.split('.');
    var fun;
    for (var i = 0; i < path.length; i++) {
        if (i == 0) {
            func = window[path[0]];
        }
        else {
            func = func[path[i]]
        }
    }
    return func;
}


function smartParseFloat(number, to_fixed) {
    // Wrapper around parseFloat aimed to deliver only numbers

    var val = parseFloat(number);
    if (isNaN(val)) return 0;
    else {
        if (to_fixed > 0 && to_fixed <= 20) return val.toFixed(to_fixed);
        else return val
    }

}

function capfirst(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function isTotalField(field_name, total_fields) {
    total_fields = total_fields || [];
    if (total_fields.indexOf(field_name) != -1) {
        return true;
    } else {
        return field_name.substring(0, 2) == '__';
    }
}


(function ($) {


    $.ra = function (options) {
        var opts = $.extend({}, $.ra.defaults, options);

        function TAB_SUPPORT() {
            //support for enter key as a navigation
            var focusables = $(':focusable');
            $('input').not('[ra_autocomplete_bind="true"]').not('[type="search"]').not('#top_search_box')
                .on("keydown", function (event) {
                    if (event.keyCode == 13) {
                        var current = focusables.index(this);
                        var check = false;
                        while (check == false) {
                            var next = getNext(current);
                            var readOnly = $(next).attr('readonly');

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

        function post_document(input, form_data, post_settings) {
            post_settings = post_settings || '';
            if (typeof form_data == 'undefined') {
                form_data = $('form').serialize();
            }
            form_data += post_settings + '&partial_html=true';
            blockDiv();
            $.post(document.location, form_data, function (data) {
                if (data['status_code'] == 200) {
                    applyJSONState(data);
                    if (typeof data.error != 'undefined') {
                        notify_error();
                    } else {
                        notify_success();
                    }
                    focus_first();
                    unblockDiv();
                } else if (data['status_code'] == 201) {
//                    notify_redirection();
                    if (data['full_page']) {
                        window.location = data['live_url'];
                    } else {
                        load_partial_html(data['live_url']);
                    }
                    notify_success();
//                    window.location = data['live_url'];
                }
                else {
                    unblockDiv();
                }

            }).fail(function () {
                notify_error();
                unblockDiv();
            })

        }


        return {
            enterTabSupport: TAB_SUPPORT,
            post_document: post_document,

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

        

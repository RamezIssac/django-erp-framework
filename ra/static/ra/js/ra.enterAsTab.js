/**
 * Created by ramez on 6/14/15.
 */

(function ($) {
    $.ra.enterAsTab = function (opts) {
        function getNext(current) {
            return focusables.eq(current + 1).length ? focusables.eq(current + 1) : focusables.eq(0);
        }

        opts = opts || {};
        var focusableSelector = opts['focusableSelector'] || ':focusable:not([readonly]):not([disabled]):not(a[ra-focus!="true"])';
        var inputSelector = opts['inputSelector'] || 'input:not([readonly]):not([disabled]):not([type=submit])';
        var select2Support = opts['select2Support'] || false;
        //support for enter key as a navigation
        var focusables = $(focusableSelector);
        //not('[ra_autocomplete_bind="true"]').not('[type="search"]').not('#top_search_box')
        if (select2Support) {

            $('select').on('select2:select', function () {
                var current = focusables.index(this);
                var check = false;

                var next = getNext(current);

                //$(this).trigger(jQuery.Event('keydown', {which: 13}));

                //var next = get_next_focusable($(this).prev(), focusables);
                if (next.is('select')) {
                    next = next.next().find('.select2-selection');
                }
                setTimeout(function () {
                    next.focus();
                    //next.focus();
                    next.select();
                }, 10)


            });
        }

        $(inputSelector)
            .on("keypress", function (event) {
                if (event.keyCode == 13) {
                    //console.log('Here');
                    var current = focusables.index(this);
                    var check = false;
                    while (check === false) {
                        var next = getNext(current);
                        var $next = $(next);
                        var readOnly = $next.attr('readonly');

                        if (typeof readOnly == 'undefined' && $next.is(':visible') === true) {
                            check = true;
                        }
                        var elem_name = $next.attr('name') || '';
                        //if (elem_name != 'undefined') {
                        if (elem_name.indexOf('DELETE') != -1) {
                            check = false;
                        }
                        //}
                        current++;
                    }

                    //if (next.is('select') && select2Support) {
                    //
                    //    next = next.next().find('.select2-selection');
                    //}

                    //if (next.is('a') && next.hasClass('raAddFormsetRow')) {
                    //    next.trigger('click');
                    //    event.preventDefault();
                    //    return
                    //}
                    next.focus();
                    next.select();
                    event.preventDefault();
                }


            });
    };

    $.ra.enterAsTab.defaults = {}

})(jQuery);
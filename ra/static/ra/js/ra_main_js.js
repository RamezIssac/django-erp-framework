/**
 * Created by ramez on 12/27/14.
 */

function adjustNumberWidget() {
    $('input[type=number]').on('focus', function (e) {
        $(this).on('mousewheel.disableScroll', function (e) {
            e.preventDefault();
            var scrollTo = (e.originalEvent.wheelDelta * -1) + $(document.documentElement).scrollTop();
            $(document.documentElement).scrollTop(scrollTo);
        })
    }).on('blur', function (e) {
        $(this).off('mousewheel.disableScroll')
    });
}

function focus_first($div) {
    $div = $div || $('#ra_page_content');
    $div.find('input:visible').not(':disabled').not('.hasDatepicker').not('.timeinput').first().select().focus();
}
function init() {
    adjustNumberWidget();
}

function partialInit() {
    focus_first();
}


var RA_Main = function () {
    var adjustNumber = adjustNumberWidget;

    return {
        init: function () {
        },
        partialInit: partialInit,
    }
}();




/**
 * Created by ramez on 9/30/15.
 */
function implement_sticky_div() {
    var s = $("#sticker");
    if (s.length != 0) {
        var pos = s.position();
        $(window).scroll(function () {
            var windowpos = $(window).scrollTop();
            if (windowpos >= pos.top) {
                s.addClass("stick");
            } else {
                s.removeClass("stick");
            }
        });
    }
}
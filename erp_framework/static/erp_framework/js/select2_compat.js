// django.contrib.admin's jquery.init.js calls jQuery.noConflict(true), which
// clears window.jQuery before select2.full.js loads. As a result, select2
// falls through to factory(undefined) and never attaches to django.jQuery.
// This shim restores window.jQuery = django.jQuery for the duration of the
// select2.full.js load, so AJAX autocomplete widgets work under Jazzmin.
(function () {
    if (
        typeof django !== 'undefined' &&
        django.jQuery &&
        typeof window.jQuery === 'undefined'
    ) {
        window.jQuery = django.jQuery;
    }
})();

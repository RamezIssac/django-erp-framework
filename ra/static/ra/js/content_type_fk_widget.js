/**
 * Created by ramez on 2/1/17.
 */

$(document).ready(function () {
    var $content_type = $('[name=content_type]');
    var $object_id = $('[name=object_id]');
    var $object_slug = $('[name=object_slug]');
    var $object_slug_parent = $object_slug.parent('div');
    var checkurl = $content_type.attr('data-check-url');
    var reverseCheckUrl =$content_type.attr('data-reverse-check-url');


    $object_slug.on('keypress', function (e) {
        if (e.keyCode == 13) {
            var data = {
                content_type: $content_type.val(),
                object_slug: $object_slug.val()
            };
            $.get(checkurl, data, function (data) {
                $object_slug_parent.find('i').remove();
                if (data.result === 'OK') {
                    $object_id.val(data.object_id);
                    $object_slug_parent.append("<i class='icon-checkmark'></i>");
                } else {
                    $object_id.val('');
                    $object_slug_parent.append("<i class='icon-cross2'></i>");
                }
            })
        }
    });

    if ($object_id.val() != '') {
        // This is a change form, we need to get the slug and its data
        var data = {
            content_type: $content_type.val(),
            object_id: $object_id.val()
        };

        $.get(reverseCheckUrl, data, function (data) {
            $object_slug_parent.find('i').remove();
            if (data.result === 'OK') {
                $object_slug.val(data.object_slug);
                $object_slug_parent.append("<i class='icon-checkmark'></i>");
            } else {
                $object_slug_parent.append("<i class='icon-cross2'></i>");
            }
        })

    }
});


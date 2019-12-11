/**
 * Created by ramez on 1/7/15.
 */


(function ($) {

    var slug_verbose = $.ra.defaults.messages.slug_verbose;
    var title_verbose = $.ra.defaults.messages.title_verbose;
    var choice_verbose = $.ra.defaults.messages.choice;
    var choiceMade = $.ra.defaults.messages.choiceBeenMade;
    var $multiSelectorInput = null;

    function MultiSelectorHandler() {

        $('[data-reveal-id=overlay_modal]').on('click', function (e) {
            $multiSelectorInput = $(this);
//        _current_model_trigger = $(this);
            e.preventDefault();
            var model_name = $multiSelectorInput.attr('ra_model');
            loadModalData(model_name);

        });
    }

    function overlay_select_control(command) {

        $('#overlay_table :checkbox').each(function () {
            var $this = $(this);
            if (command == 'all') {
                $this.prop('checked', true);
            }
            else if (command == 'none') {
                $this.prop('checked', false);
            }
            else if (command == 'inverse') {
//            //console.log('checked',$this.checked) ;#}
//            //console.log('prop',$this.prop('checked')) ;#}

                if ($this.prop('checked') == true) {
                    $this.prop('checked', false);
                }
                else {
                    $this.prop('checked', true);
                }
            }

        });
    }

    function apply_from_to_code() {
        var rows = $('#overlay_table tbody >tr');
        var from_code = $('#from_code').val();
        var to_code = $('#to_code').val();

        var columns;

        for (var i = 0; i < rows.length; i++) {
            var $currentRow = $(rows[i]);
            columns = $currentRow.find('td');
            var check = $currentRow.find('input');
            var id = $(columns[1]).html();
            if (id >= from_code && id <= to_code) {
                check.prop('checked', true);
            }
            else {
                check.prop('checked', false);
            }
        }


    }

    function _getMultiSelectorIdContainer($multiSelectorinput) {
        return $multiSelectorinput.parents('.ra-fk-input-group').find('.raFkPk');
    }

    function applySelection() {
        var result = getSelectedEntities();
        var $inputContainer = $multiSelectorInput.parents('.ra-fk-input-group');
        $inputContainer.find('.raFkPk').val(result);
        var slugContainer = $inputContainer.find('.raFkSlug');
        var titleContainer = $inputContainer.find('.raFkTitle');
        if (result.length > 1) {
            slugContainer.attr('disabled', true);
            titleContainer.text(choiceMade);
        }
        else {
            slugContainer.attr('disabled', false);
            titleContainer.text('');
        }

        $('#close_autocomplete_modal').trigger('click');
    }

    function getSelectedEntities() {
        //hack to remove datatable filter , if it's not removed , the reyturned results were not to be the expected
        // we will be looking at the filtered table for checked not the all table !
        var _t = $('#overlay_table').DataTable({retrieve: true});
        _t.search('')
            .columns().search('')
            .draw();
        var rows = $('#overlay_table tbody >tr');
        var columns;
        var values = '';
        for (var i = 0; i < rows.length; i++) {
            columns = $(rows[i]).find('td');
            var check = $(rows[i]).find('input');
            if (check.prop('checked')) {
                values += $(columns[0]).html() + ',';
            }
        }
        return values;
    }

    function _getModalStructure(response) {
        var $modal = $($.ra.autocomplete.defaults.modalTemplate); // _get_modalContainer().append($($.ra.autocomplete.defaults.modalTemplate));
        var columns = response.columns;
        var column_names = response.column_names;
        var col_th = '';
        for (var i = 0; i < columns.length; i++) {
            col_th += '<th class="' + columns[i] + '">' + column_names[i] + '</th>';
        }
        var table_class = $.ra.datatable.defaults.tableCssClass;

        $modal.find('.select-modal-content').html('<table cellpadding="0" cellspacing="0" border="0" class="' + table_class +'" id="overlay_table">' +
            '<thead><tr> <th class="hide"> id </th> ' + col_th + ' <th>' + choice_verbose + '</th> </tr> </thead>' +
            //'<tfoot> <tr><th class="hide"> id </th> ' + col_th + ' <th>' + choice_verbose + '</th> </tr><tfoot>' +
            '<tbody></tbody></table>'
        );
        $modal.find('#autocompleteSelectAll').on('click', function () {
            overlay_select_control('all');
        });
        $modal.find('#autocompleteSelectNone').on('click', function () {
            overlay_select_control('none');
        });
        $modal.find('#autocompleteInvertSelection').on('click', function () {
            overlay_select_control('inverse');
        });
        $modal.find('#autocompleteApply').on('click', function () {
            applySelection();
        });
        $modal.find('#apply_from_to_code').on('click', function () {
            apply_from_to_code();
        });

        return $modal;
    }

    function printResponseToTable(response) {

    }

    function loadModalData(e) {

        blockInput($multiSelectorInput);

        $.get(get_base_autocomplete_url() + e + '/all/', function (response) {
            var $modal = _getModalStructure(response);

            // the ',' is added for accurate search :
            var previous_results = ',' + _getMultiSelectorIdContainer($multiSelectorInput).val();
            // Example: previous_results = '11,1,'. A .indexOf('1,') would return 1 where right answer would be 3

            var table_structure = '';
            var response_data = response.data;
            var columns_length = response.columns.length;
            var columns = response.columns;
            for (var i = 0; i < response_data.length; i++) {
                var table_row = "<td class='hide'>" + response_data[i].pk + "</td>";
                for (var z = 0; z < columns_length; z++) {
                    table_row += "<td>" + response_data[i][columns[z]] + "</td>";
                }
                //table_row += "<td>" + response_data[i].slug + "</td>";
                //table_row += "<td>" + response_data[i].title + "</td>";
                if (previous_results.indexOf(',' + response_data[i].pk + ',') > -1) {
                    table_row += "<td> <input type='checkbox' checked=true /> </td>";
                }
                else {
                    table_row += "<td> <input type='checkbox' /> </td>";
                }
                table_row = "<tr>" + table_row + "</tr>";

                table_structure += table_row;
            }


            $modal.find('.select-modal-content table tbody').html(table_structure);
            $modal.find('.select-modal-content').append('<span id="current-model" value="' + e + '"/>');


            overlay_table = $('.select-modal-content table').DataTable({

                "scrollY": "250px",
                "scrollCollapse": true,
                "paging": false,
                initComplete: function () {
                    var prevent_on = [0, 1, 2, this.api().columns()[0].length - 1];
                    this.api().columns().every(function () {
                        var column = this;
                        var i = column.index();
                        if (prevent_on.indexOf(i) == -1) {
                            var select = $('<select><option value=""></option></select>');
                            select.appendTo($(column.footer()).empty())
                                .on('change', function () {
                                    var val = $.fn.dataTable.util.escapeRegex(
                                        $(this).val()
                                    );

                                    column
                                        .search(val ? '^' + val + '$' : '', true, false)
                                        .draw();
                                });

                            column.data().unique().sort().each(function (d, j) {
                                if (d != '')
                                    select.append('<option value="' + d + '">' + d + '</option>')
                            });
                        }
                        else {
                            $(column.footer()).empty()
                        }
                    });
                }

            });
            setTimeout(function () {
                overlay_table.columns.adjust()
            }, 500);
            unblockDiv($multiSelectorInput);
            $('#autocompleteMultiSelector').modal();
        })
            .fail(function(data){
                unblockDiv($multiSelectorInput);
                notify_error("Couldn't load resource")
            });
    }


    function get_base_autocomplete_url() {
        return $.ra.autocomplete.defaults.autocomplete_url;
    }

    function default_url_factory(model_name, term, exact) {
        var strReturn = get_base_autocomplete_url() + model_name + '/' + term + '/';
        if (exact == true) {
            strReturn += 'exact/'
        }
        return strReturn;

    }

    function get_title_container($input) {
        return $input.siblings('.raFkTitle');
    }

    function get_id_container($input) {
        return $input.siblings('.raFkPk');
    }

    function autocompleteResponseHandler(data, input, id_container, slug_container, title_container) {


    }


    function get_input_attrs(input) {
        var $input = $(input);
        var attrs = {};
        var model_name = $input.attr('ra_autocomplete_model');// 'expense';

        var url_factory_function = $input.attr('ra_url_factory');
        if (typeof url_factory_function == 'undefined') {
            if (typeof window['custom_url_factory'] === "function") {
                url_factory_function = 'custom_url_factory';
            }
            else {
                url_factory_function = 'default_url_factory';
            }
        }

        attrs.url_factory_function = url_factory_function;
        attrs.model_name = model_name;
        return attrs;
    }

    function _getautocomplete_url(function_name, attrs, term, isExact, input) {
        isExact = typeof isExact == 'undefined' ? false : isExact;
        if (function_name == 'default_url_factory') {
            return window['jQuery']['ra']['autocomplete']().default_url_factory(attrs.model_name, term, isExact, input);
        }
        return window[attrs.url_factory_function](attrs.model_name, term, isExact, input);
    }

    function fireAutocompleteResponseHandler($input, data) {
        var _autocompleteResponseHandler = $input.attr('ra_autocomplete_response_handler');
        if (typeof _autocompleteResponseHandler == 'undefined') {
            if (typeof window['custom_autocomplete_response_extension'] === "function") {
                //todo document javascript naming convention , any function that is 'set' from server , name is following python style
                _autocompleteResponseHandler = 'custom_autocomplete_response_extension';
            }
            else {
                return;
//                _autocompleteResponseHandler = 'autocompleteResponseHandler';
            }
        }
//        console.log('firing the Response');
        window[_autocompleteResponseHandler](data, $input);
    }

    function setIdSlugTitle($input, id, slug, title, data) {

        get_id_container($input).attr('value', id);
        $input.attr('value', slug);
        var decorated_title = '';
        if (id != '') {
            decorated_title = get_decorated_title(data.url, data.title);
        }
        get_title_container($input).html(decorated_title);

        fireAutocompleteResponseHandler($input, data);

    }

    function get_decorated_title(url, title) {
        if (url) return '<a href="' + url + '" target="_blank">' + title + '</a>';
        else return title;
    }

    function bind_ra_autocomplete(div) {
        div = typeof div == 'undefined' ? $(document) : div;
//        console.log('binding autocomplete');
        var selector = div.find('[ra_autocomplete_bind="true"]');
        var autocomplete_obj = {
            source: function (request, response) {
                var attrs = get_input_attrs(this.element);

                var autocompleteUrl = _getautocomplete_url(attrs.url_factory_function, attrs, request.term, false, $(this.element));
//                    window[attrs.url_factory_function](attrs.model_name, request.term, false, $(this.element));

                $.getJSON(autocompleteUrl, function (data) {
                    response($.map(data.data, function (value, key, data) {
                        return {
                            label: value.slug + ' | ' + value.title,
                            value: value.pk,
                            url: value.url,
                            slug: value.slug,
                            name: value.title
                        };
                    }));
                });
            },
            focus: function (event, ui) {
                var $this = $(this);
                var title_container = get_title_container($this);
                var decorated_title = get_decorated_title(ui.item.url, ui.item.name);
                title_container.html(decorated_title);
                $this.val(ui.item.slug);
                return false;
            },
            select: function (event, ui) {
                var $this = $(this);
                var id_container = get_id_container($this);
                id_container.attr('value', ui.item.value);
                var title_container = get_title_container($this);
                var decorated_title = get_decorated_title(ui.item.url, ui.item.name);
                title_container.html(decorated_title);
                $this.val(ui.item.slug);
                $this.removeClass('autocomplete_error');
                $this.attr('confirmed', true);
                return false;
            },
            open: function (event, ui) {
                $(".ui-autocomplete").css("z-index", 100000);
            },
            minLength: 1,
            delay: 200,
            //todo, link with the rtl option
            //position: {
            //    my: "right top",
            //    at: "right bottom"
            //},

        };
        if ($.ra.rtl) {
            autocomplete_obj.position = {
                my: "right top",
                at: "right bottom"
            }
        }
        selector.autocomplete(autocomplete_obj);
    //        .autocomplete("instance")._renderItem = function(ul, item) {
    //
    //    return $("<li>").append("<span class='text-semibold'>" + item.label + '</span>' + "<br>" + '<span class="text-muted text-size-small">' + item.desc + '</span>').appendTo(ul);
    //};

        selector.on('keydown', function (event) {
            var $this = $(this);
            if (event.keyCode == 13) {
                event.preventDefault();
                // the case the user write the whole slug & presses enter
                // we have to ask the server if this code is correct
                var _autocompleteResponseHandler = $this.attr('ra_autocomplete_response_handler');
                var model_name = $this.attr('ra_autocomplete_model');

                if ($this.val() == '') {
                    //user removes entered slug , emptying the field.
                    setIdSlugTitle($this, '', '', '', [], model_name);
                    $this.removeClass('autocomplete_error');

                } else if ($this.attr('confirmed') == "false" || _autocompleteResponseHandler != '') {

                    react_enter_key($this);
                }

                focusNextElement($this);

            }
            else {
                $this.attr('confirmed', false);

            }

        });

        MultiSelectorHandler();

    }

    function focusNextElement($this) {
        // todo wire with enter as tab
        var inputs = $('input:focusable');
        var i = inputs.index($this);
        var ctr = inputs[i + 1];
        ctr.focus();
        ctr.select();
        return ctr;
//        var next_element = $($this.parents().next()[1]).find('input:visible:eq(0)');
//        if (next_element.length == 0) next_element = get_next_focusable(this);
//
//        if (next_element.attr('disabled') == 'disabled') {
//            $(next_element.parents().next()).find('input:visible:not([disabled]):eq(0)').focus();
//        }
//        else {
//            next_element.focus();
//        }
    }

    function react_enter_key($input) {
        var id = null;
        var slug = null;
        var title = null;
        var attrs = get_input_attrs($input);
        var model = attrs.model_name;

        var url_factory_function = $input.attr('ra_url_factory');

        var autocompleteUrl = _getautocomplete_url(attrs.url_factory_function, attrs, $input.val(), true, $input);

        $.getJSON(autocompleteUrl, function (response) {
            var data = response.data;
            if (data.length > 0) {

                data = data[0];
                id = data.pk;
                slug = data.slug;
                title = data.title;
                $input.removeClass('autocomplete_error');
                setIdSlugTitle($input, id, slug, title, data);

            }
            else {
                //                console.log('no data found !')
                id = '';
                slug = $input.val();
                title = '';
                $input.addClass('autocomplete_error');
                setIdSlugTitle($input, id, slug, title, data);
            }
        }).fail(function () {
            id = '';
            slug = $input.val();
            title = '';
            $input.addClass('autocomplete_error');
            setIdSlugTitle($input, id, slug, title, data);
        });

    }

    function _get_modalContainer() {
        var modalContainer = $($.ra.autocomplete.defaults.modalContainerTemplate);
        var check = $('#' + modalContainer.attr('id'));
        if (check.length > 0) {
            check.html('');
            return check;
        }
        else {
            $('body').append(modalContainer);
            return $('#' + modalContainer.attr('id'));
        }
    }

    $.ra.autocomplete = function (options) {
        return {
            bind: bind_ra_autocomplete,
            default_url_factory: default_url_factory,
            url_factory: default_url_factory,
        }
    };

    $.ra.autocomplete.defaults = {
        'clickableTitle': true,
        rtl: true,
        'autocomplete_url': '/autocomplete/',
        'modalTemplate': '#autocompleteMultiSelector',
        modalContainerTemplate: '<div id="autocompleteMultiSelectorContainer"></div>'


    }
}(jQuery));

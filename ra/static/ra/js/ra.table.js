/**
 * Created by ramez on 7/3/17.
 */

function constructFullTable(id, css_class, cols, cols_names, data, settings, total_verbose) {
    var add_footer = false;
    var provide_total = settings.provide_total;
    var hide_columns = settings.hide_columns || [];
    if (provide_total == 'auto' || provide_total == true || typeof(provide_total) == 'undefined') {
        add_footer = true
    }
    var computed_totals = settings.computed_totals;


    var total_fields = settings.total_fields;

    // Construct an HTML table , header and footer ,WITH Body
    id = typeof id != 'undefined' ? id : 'mytable';
    cols = typeof cols != 'undefined' ? cols : false;
    cols_names = typeof cols_names != 'undefined' ? cols_names : cols;

    for (var i = 0; i < hide_columns.length; i++) {
        var index = cols.indexOf(hide_columns[i]);
        if (index !== 0) {
            cols.splice(index, 1);
            cols_names.splice(index,1);
        }
    }
    var return_val = '<table class="' + css_class + '"  width="98%" > <thead>' +
        '<tr>';
    var header_th = '';
    var footer_th = '';
    var totalCalculation = {};
    var footer_colspan = 0;
    var stop_colspan_detection = false;
    for (var i = 0; i < cols.length; i++) {
        var col = cols[i];
        header_th += '<th data-id="' + cols[i] + '">' + cols_names[i] + '</th>';
        if (isTotalField(col, total_fields) && provide_total) {
            totalCalculation[col] = 0;
        }
    }
    var tbody = '<tbody>';
    for (i = 0; i < data.length; i++) {
        tbody += '<tr>';
        for (var x = 0; x < cols.length; x++) {
            var col = cols[x];
            var line = data[i];
            if (isTotalField(col, total_fields) && provide_total) {
                totalCalculation[col] += parseFloat(line[col])
            }
            tbody += '<td class="' + cols[x] + '">' + line[col] + '</td>'
        }
        tbody += '</tr>';
    }
    for (i = 0; i < cols.length; i++) {

        if (isTotalField(cols[i], total_fields)) {
            stop_colspan_detection = true;
        }
        if (stop_colspan_detection == false) {
            footer_colspan += 1;
        }
        else {
            var tfoot_val = '';
            if (_.has(computed_totals, cols[i])) {
                tfoot_val = computed_totals[cols[i]];
            } else {
                tfoot_val = totalCalculation[cols[i]];
                try {
                    tfoot_val = tfoot_val.toFixed(2);
                } catch (err) {

                }
            }
            tfoot_val = typeof(tfoot_val) == 'undefined' ? '' : tfoot_val;
            footer_th += '<th data-id="' + cols[i] + '">' + tfoot_val + '</th>';
        }
    }

    var footer = '';
    if (add_footer == true && stop_colspan_detection == true) {
        footer = '<tfoot><tr class="tr-totals active"><th colspan="' + footer_colspan + '" style="text-align:left">' + total_verbose + '</th>' + footer_th + '</tr></tfoot>';
    }
    return_val = return_val + header_th +
        '</tr>' +
        '</thead>' + tbody + footer +
        '</table>';

    return return_val;
}
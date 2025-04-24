"use strict";
$(function() {
    var $select_el = $('#id_series'),
        $label_el = $('#div_id_start label'),
        toggle_series_help = function($el) {
            var option = $("option:selected", $el),
                help = option.data('start-event'),
                original = $label_el.data('original');

            if(original === undefined) {
                $label_el.data('original', $label_el.html());
            }

            if(help !== undefined) {
                $label_el.html(help+'<span class="asteriskField">*</span>');
            }
            else {
                $label_el.html(original);
            }
        };

    toggle_series_help($select_el);

    $select_el.on('change', function(e){
        toggle_series_help(this);
    });
});

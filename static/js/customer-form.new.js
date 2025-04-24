$(function() {
    // If the is_registered field has been changed confirm the CCO wants to make
    // this change as doing so triggers welcome message sending.
    let $is_registered = $('#id_is_registered');
    if ( $is_registered.length ) {
        let is_registered = $is_registered[0].checked;

        $('form').on('submit', function( event ) {
            if( is_registered != $('#id_is_registered')[0].checked ) {
                let confirmed = confirm(
                  "Are you sure you want to change the customer's registration status?"
                );
                if ( !confirmed ) {
                    event.preventDefault();
                }
            }
        });
    }

    // Handles market subscriptions formset
    let $market_subscriptions = $('.market-subscriptions .row');
    if ( $market_subscriptions.length ) {
        $market_subscriptions.formset({
            addCssClass: 'btn btn-primary',
            prefix: 'market_subscriptions',
            addText: 'Add another market',
            deleteText: '',
            deleteCssClass: 'js-market-remove fa-solid fa-trash mod-market-remove'
        });
    }
    $('.js-market-remove').on('mouseenter', function() {
        $(this).parent().addClass('alert-panel-delete');
    }).on('mouseleave', function() {
        $(this).parent().removeClass('alert-panel-delete');
    });

    // Initialize customer location fields
    // The customerGPS field may be double JSON encoded
    let customerGPS = JSON.parse(document.getElementById('customerGPS').textContent);
    if (typeof customerGPS === 'string') {
        customerGPS = JSON.parse(customerGPS);
    }
    if (!customerGPS || customerGPS.length === 0) {
        return;
    }
    $.getJSON('/world/borders_for_location', customerGPS, function(resp_data) {
        let border0_pk = resp_data['border0'];
        let border1_pk = resp_data['border1'];
        let border2_pk = resp_data['border2'];
        let border3_pk = resp_data['border3'];
        let non_option = {id: "", name: '---------'}

        let $el = $('select#id_border0')
        $el.find('option[value='+border0_pk+']')
           .prop('selected', true);

        $el = $('select#id_border1')
        $el.find('option[value='+border1_pk+']')
           .prop('selected', true);

        $el = $('select#id_border2');
        $el.prop('disabled', false);     // Enable the field
        if (resp_data['change_border2_options'] && resp_data['border2_options']) {
          if (!$el.prop('required')) {
            resp_data['border2_options'].unshift(non_option)
          }
          $el.replaceOptions(resp_data['border2_options']);  // Replace the menu options
        }
        $el.find('option[value='+border2_pk+']')
           .prop('selected', true);

        $el = $('select#id_border3');
        $el.prop('disabled', false);     // Enable the field
        if (resp_data['change_border3_options'] && resp_data['border3_options']) {
          if (!$el.prop('required')) {
            resp_data['border3_options'].unshift(non_option)
          }
          $el.replaceOptions(resp_data['border3_options']);
        }
        $el.find('option[value='+border3_pk+']')
           .prop('selected', true);
    });
});

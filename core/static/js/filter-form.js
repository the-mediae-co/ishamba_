(function ($, window) {
    $.fn.replaceOptions = function (options) {
        let self, $option;
        this.empty();
        self = this;

        $.each(options, function (index, option) {
            $option = $("<option></option>")
                .attr("value", option.id)
                .text(option.name);
            self.append($option);
        });
    };
})(jQuery, window);

function dataUpdatesNeeded(customer) {
    return !(customer.border0 &&
        customer.border1 &&
        customer.border2 &&
        customer.border3 &&
        customer.sex);
}

function initializeLocationMenus(usingSelect2) {
    // Create some 'global' variable to reduce repeating searches
    window.$border0_block = $('#div_id_border0.form-group');
    window.$border1_block = $('#div_id_border1.form-group');
    window.$border2_block = $('#div_id_border2.form-group');
    window.$border3_block = $('#div_id_border3.form-group');

    // If no location div's on this page, no need to initialize
    if (!window.$border0_block ||
        !window.$border1_block) {
        return;
    }
    // Set the initial state
    window.$border0_block.show().prop('disabled', false);  // Ensure that the country select is always visible
    // If a level has a selection, enable/show their submenu
    if ($('select#id_border0').val().length > 0) {
        window.$border1_block.show().prop('disabled', false);
    }
    else {
        window.$border1_block.hide();
    }
    for(let i = 1; i < 3; i++) {
        if (usingSelect2) {
            if ($('#id_border' + i).select2('data') && $('#id_border' + i).select2('data').length > 0) {
                eval('window.$border' + (i + 1) + '_block.show().prop("disabled", false);');
            }
            else {
                eval('window.$border' + (i + 1) + '_block.hide();');
            }
        }
        else {
            if ($('select#id_border' + i).val().length > 0) {
                eval('window.$border' + (i + 1) + '_block.show().prop("disabled", false);');
            }
            else {
                eval('window.$border' + (i + 1) + '_block.hide()');
            }
        }
    }
}

function updateLocationMenusStates(usingSelect2, resp_data) {
    // Set up a no-selection option for optional fields
    let non_option = {id: "", name: '---------'}
    let $el = $('select#id_border0');
    if ($el.length && resp_data && 'selected_border0s' in resp_data) {
        // Re-select the countries
        resp_data['selected_border0s'].forEach(function (element) {
            $el.find('option[value=' + element + ']')
                .prop('selected', true);
        })
        // Set the <select> labels appropriately based on what countries are selected
        if ('border0_label' in resp_data) {
            $('label[for="id_border0"]').text(resp_data['border0_label'])
        }
        if ('border1_label' in resp_data) {
            $('label[for="id_border1"]').text(resp_data['border1_label'])
        }
        if ('border2_label' in resp_data) {
            $('label[for="id_border2"]').text(resp_data['border2_label'])
        }
        if ('border3_label' in resp_data) {
            $('label[for="id_border3"]').text(resp_data['border3_label'])
        }
    }

    for(let i = 1; i <= 3; i++) {
        $el = $('select#id_border' + i);
        if ($el.length && resp_data && ('enable_border' + i) in resp_data && resp_data['enable_border' + i]) {
            // Enable the field
            let $block = eval('window.$border' + i + '_block');
            if ($block) {
                $block.show().prop("disabled", false);
                if (resp_data['change_border' + i + '_options'] && resp_data['border' + i + '_options']) {
                    if (usingSelect2) {
                        // Populate select2 (or django-select2) with new options
                        $('#id_border' + i).select2({
                            data: resp_data['border' + i + '_options'],
                            'data-placeholder': 'Click to select a ' + resp_data['border' + i + '_label'],
                            placeholder: 'Click to select a ' + resp_data['border' + i + '_label']
                        });
                    } else {
                        // If not select2, add the non_option to the top and manually replace the select options
                        if (!$el.prop('required')) {
                            resp_data['border' + i + '_options'].unshift(non_option);
                        }
                    }
                    // In either case, replace the options
                    $el.replaceOptions(resp_data['border' + i + '_options']);
                }
            }
            // Re-select the items that the server believes were selected
            resp_data['selected_border' + i + 's'].forEach(function (element) {
                $el.find('option[value=' + element + ']').prop('selected', true);
            });
        } else {
            // Disable this border selector
            $('#id_border' + i + ' option').prop('selected', false);  // Remove any user selections that were made
            let $block = eval('window.$border' + i + '_block');
            if ($block) {
                $block.hide();
            }
        }
    }
}

// Handles the asynchronous submission of the CustomerFilterFormView to retrieve
// the number of customers currently selected as recipients. Also interacts
// with the in-call AngularJS code to provide location update menus.

// We need to use this form instead of $(function ()) because we need the
// AngularJS forms on the in-call UI to be populated before initialization.
$( window ).on( "load", function() {
    // We keep track of the current request to ensure that we don't have multiple
    // in-flight requests as even with _.debounce() due to the slow nature of the
    // network and backend.
    let $current_request = null;

    // Check if we're using the django-select2 multiselect form items for location selections
    let foundSelect2 = false;
    for(let i = 0; i < 4; i++) {
        if ($('#div_id_border' + i + ' > div > .select2.select2-container').length > 0) {
            foundSelect2 = true;
        }
    }
    // const usingSelect2 = $('.select2.select2-container > .selection > .select2-selection.select2-selection--multiple').length > 0;
    const select2Locations = foundSelect2;

    // Initialize menu states, if they are on this page
    if ($('#div_id_border0').length > 0) {
        initializeLocationMenus(select2Locations);
    }

    const findFormField = (form_data, field) => {
        return form_data.find((row) => {
            if (row['name'] === field) {
                return row;
            }
        });
    };
    const ajaxGetForm = function ($form, $submit, options) {
        let form_data = $form.serializeArray();
        if (options && options.customerGPS) {
            form_data.push({name: 'lat', value: options.customerGPS['lat']});
            form_data.push({name: 'lng', value: options.customerGPS['lng']});
        }
        let url = $form.attr('action');
        let method = $form.attr('method');
        let filtered_data = form_data.filter(function (field) {
            return !!field.value;  // Only include fields with values
        });
        if (url === undefined || url === '') {
            // If no url specified in the form, see if a global was set
            if (typeof g_updates_url !== 'undefined' && g_updates_url) {
                url = g_updates_url;  // If we're in the in_call_controller and the global updates url is specified, use it
            }
        }
        if (method === 'get' && 'URLSearchParams' in window) {
            // Modify the url, updating the location params
            let searchParams = new URLSearchParams(window.location.search)
            for (let i = 0; i < 4; i++) {
                // If a border parameter exists, replace it with the new value
                let foundRow = findFormField(filtered_data, 'border' + i);
                if (foundRow) {
                    searchParams.set('border' + i, foundRow['value'] || '');
                }
                else {
                    searchParams.delete('border' + i);
                }
            }
            url = window.location.pathname + '?' + searchParams.toString();
        }
        if (url === undefined || url === '') {
            // If url still not defined, bail
            console.log("ERROR: No URL for ajaxGetForm ajax call in filter-form.js")
            return;
        }
        // Extract the csrf token from the form
        let csrf = $('input[name="csrfmiddlewaretoken"]').attr('value')
        // If the form didn't have one, check the globals
        if (!csrf && g_csrftoken) {
            csrf = g_csrftoken
        }
        if (options) {
            // Add details of what field was changed by the user
            filtered_data.push({name: "changed_field", value: options.changed_field});
            filtered_data.push({name: "is_multiselect", value: options.is_multiselect});
        }
        $('#div_saved_toast').hide();
        $('#div_saving_toast').show();
        // Make the ajax request
        $current_request = $.ajax({
            type: method,
            url: url,
            headers: {'X-CSRFToken': csrf},
            data: filtered_data,
            success: null
        })
        .done(function (resp_data) {
            // Success
            if (resp_data != null && Object.keys(resp_data).length !== 0) {
                // If data was returned in the response
                if (resp_data['rendered_customer_count']) {
                    $('#customer-count').html(resp_data['rendered_customer_count'].toLocaleString());
                }
                updateLocationMenusStates(select2Locations, resp_data);
                if (options && options.linkMenusAndMap) {
                    // If the leaflet map exists, update the customer's location based on this menu selection event
                    if (typeof window.iShambaGeoMap !== 'undefined' && typeof window.iShambaGeoMap.updateLeafletMapLayers === "function") {
                        if (!options.alreadyUpdatedMap) {
                            window.iShambaGeoMap.updateLeafletMapLayers(resp_data, options.setCustomerToCentroid);
                        }
                    }
                }
                $('#div_saving_toast').hide();
                $('#div_saved_toast').show().delay(1000).fadeOut(2000);
            }
        })
        .always(function () {
            $current_request = null;
            if ($submit) {
                $submit.prop("disabled", false);
            }
        });
    }

    // Execute ajaxGetForm at most once per half second (500ms)
    let debouncedGetForm = _.debounce(ajaxGetForm, 500);

    $('form#updates_form, form#filter-form').on('change', function (e, params) {
        // Check if this change event originated as a click on the leaflet-control-layers-selector
        if (e.target.className.startsWith('leaflet-control')) {
            return;
        }
        let $form = $(this);
        let $submit = $('input#submit-id-submit');
        let changed_field = e.target.name;
        e.target.selectedOptions
        let new_selections = [];
        if (e.target.selectedOptions && e.target.selectedOptions.length > 0) {
            for (i of e.target.selectedOptions) {
                new_selections.push(i.value);
            }
        }
        new_selections = new_selections.join(',');
        let is_multiselect = e.target.multiple;

        // if we have an in-flight request but have changed our filtering options
        // abort the in-flight request.
        if ($current_request) {
            $current_request.abort();
        }

        $submit.attr('disabled', 'disabled')
            .addClass('disabled');

        if (e.detail) {
            // Set defaults of not in options
            if (e.detail.setCustomerToCentroid === undefined) {
                e.detail.setCustomerToCentroid = true;
            }
            if (e.detail.alreadyUpdatedMap === undefined) {
                e.detail.alreadyUpdatedMap = false;
            }
        }
        debouncedGetForm($form, $submit, e.detail);
    });
});

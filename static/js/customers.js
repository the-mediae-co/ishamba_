$(function() {
    $( document ).ready(function() {
        // Force the filter panel to hide by default, even if there are request.GET parameters
        let filterPanel = $('#customerFilterCard');
        filterPanel.collapse('hide');
        filterPanel.addClass('collapse');

        // In the crispyform content, the generated HTML has <div>s that contain the multiselect menus
        // just below their corresponding <label>s. Give them an id so we can show/hide them more easily.
        $('#div_id_border1.form-group > div').attr('id', "id_border1_content");
        // Ensure that the country select is always visible
        $('div#div_id_border0').show();
        // If there's no country selection, then initially hide the submenu
        if ($('select#id_border0').val().length > 0) {  // If a country was selected
            $('div#id_border1_content').show();         // Show the county/region <select>
        }
        else {
            $('div#id_border1_content').hide();
        }

        $('select#id_border0').on('change', function (evt, params) {
            // If border0 was changed, and there is a selected country, show the sub-menu
            if ($('select#id_border0').val().length > 0) {  // If a country was selected
                $('div#id_border1_content').show();         // Show the county/region <select>
            }
            else {
                $('div#id_border1_content').hide();
            }
            // If different countries were selected, reset the county/region selections
            // Unnecessary with select2
            // $('select[name="border1"]').val(''); //.trigger('change');
        });

        // Initialize the selected customers and counter
        let selected_customers_count = document.getElementById('selected_customers_count');
        let selected_customers = document.getElementById('selected_customers');
        if (selected_customers_count) {
            const initial_selected_customers_count = JSON.parse(selected_customers_count.textContent);
            document.getElementById('reset-selections').hidden = (initial_selected_customers_count === 0);
            document.getElementById('submit-id-bulk-sms').disabled = (initial_selected_customers_count === 0);
            setExportButtonState(initial_selected_customers_count);
        }
        if (selected_customers) {
            const initial_selected_customers = JSON.parse(selected_customers.textContent);
            let pageSelections = 0;
            for (let t of initial_selected_customers) {
                let cb = document.getElementById('id_customer_' + t);
                if (cb != null) {
                    cb.checked = true;
                    pageSelections += 1;
                }
            }
            if (pageSelections === 25) {
                // If all records on this page were selected, check the checkbox in the header
                document.getElementById('bulk-select-all').checked = true;
            }
        }
    });

    // when panel is revealed. 'shown.bs.collapse' is a Bootstrap event
    // $('#filterPanel').on('shown.bs.collapse', function(e) {
    //     $(this).find('.selectmultiple').chosen("destroy").chosen();
    // });

    $('#bulk-select-all').on('click', function(e) {
        $("input[name='bulk-customers']").prop("checked", $(this).prop("checked") === true);
        selectCustomers(null);
    });

    // the 'reset filter form' button
    $('#reset-filter-form').on('click', function (e) {
        // Reset the form. Note that this resets it to the parameters provided with the GET. I.e., not purely reset.
        document.getElementById("filter-form").reset();
        // reset the text fields
        $("#filter-form input[type=text]").val("")
        // reset the select fields
        $("#filter-form select").prop("selectedIndex", -1).find('option:selected').removeAttr('selected')
        // Reset the select2 elements
        $('#id_border1, #id_categories, #id_customer_id, #id_last_editor').val('').trigger('change')
        // and now re-submit the form
        // $("#filter-form").trigger("submit");
    });
});

function selectCustomers(cb) {
    // Extract the csrf token from the form
    let csrf = $('input[name="csrfmiddlewaretoken"]').attr('value')
    let filtered_data = {};
    // Add any checked Customers to the filtered_data set
    $("input:checkbox[name='bulk-customers']").each(function(){
        let customer_id = $(this).val();
        filtered_data[customer_id] = $(this)[0].checked;
    });
    // Make an ajax POST to update the server's session data
    let current_request = $.ajax({
        type: "POST",
        headers: {'X-CSRFToken': csrf},
        data: JSON.stringify(filtered_data),
        success: null
    })
    .done(function (resp_data) {
        // Success
        let customers_selected_count = resp_data['customers_selected_count'];
        if (customers_selected_count > 0) {
            // If the total number selected > 0 was returned in the server response
            let customers_name = 'Customer';
            if (customers_selected_count > 1) {
                customers_name += 's'
            }
            // Update and show the 'Customers Selected' UI
            document.getElementById('selected-customers-count').innerHTML = customers_name + ' Selected: ' + customers_selected_count.toLocaleString();
            document.getElementById('reset-selections').hidden = false;
            document.getElementById('submit-id-bulk-sms').disabled = false;
        }
        else {
            // Update and hide the 'Customers Selected' UI
            document.getElementById('selected-customers-count').innerHTML = 'Customers Selected: ' + customers_selected_count;
            document.getElementById('reset-selections').hidden = true;
            document.getElementById('submit-id-bulk-sms').disabled = true;
        }
        setExportButtonState(customers_selected_count);
    });
}

function selectAllCustomers(cb) {
    $("input[name='bulk-customers']").prop("checked", true);
    $('#bulk-select-all').prop("checked", true);
    // Extract the csrf token from the form
    let csrf = $('input[name="csrfmiddlewaretoken"]').attr('value')
    // Make an ajax POST to update the server's session data
    let current_request = $.ajax({
        type: "POST",
        headers: {'X-CSRFToken': csrf},
        data: JSON.stringify("all"),
        success: null
    })
    .done(function (resp_data) {
        // Success
        // Update and show the 'Customers Selected' UI
        document.getElementById('selected-customers-count').innerHTML = 'Customers Selected: ' + resp_data['customers_selected_count'].toLocaleString();
        document.getElementById('reset-selections').hidden = false;
        document.getElementById('submit-id-bulk-sms').disabled = false;
        setExportButtonState(resp_data['customers_selected_count'].toLocaleString());
    });
}

function clearSelections(cb) {
    $("input[name='bulk-customers']").prop("checked", false);
    $('#bulk-select-all').prop("checked", false);
    // Extract the csrf token from the form
    let csrf = $('input[name="csrfmiddlewaretoken"]').attr('value')
    // Make an ajax POST to update the server's session data
    let current_request = $.ajax({
        type: "POST",
        headers: {'X-CSRFToken': csrf},
        data: JSON.stringify(null),
        success: null
    })
    .done(function (resp_data) {
        // Success
        // Update and hide the 'Customers Selected' UI
        document.getElementById('selected-customers-count').innerHTML = 'Customers Selected: ' + resp_data['customers_selected_count'].toLocaleString();
        document.getElementById('reset-selections').hidden = true;
        document.getElementById('submit-id-bulk-sms').disabled = true;
        setExportButtonState(resp_data['customers_selected_count']);
    });
}


function setExportButtonState(selectedRecordsCount) {
    let emailButton = document.getElementById("export-button");
    if (emailButton) {
        let recordCountString = selectedRecordsCount.toLocaleString();
        emailButton.disabled = Number(selectedRecordsCount) === 0;
        emailButton.innerText = "Email " + recordCountString + " filtered records";
    }
}


function generateEmailReport(button) {
    let form = $("form#customer-export")
    let form_data = form.serializeArray();
    form_data.push({name: 'export-customers', value: 'export-customers'});
    let filtered_data = form_data.filter(function (field) {
        return !!field.value;  // Only include fields with values
    });
    $('#export-success-toast').html('Status: Submitted...').show();
    $.post(
        '#',
        filtered_data,
    ).done(function(data, status, xhr){
        $('#export-success-toast').html('Status: Success!<br/>Check your ' + data['user_email'] + ' email ').fadeOut(20000);
        console.log('Success! Sent report to: ' + data['user_email']);
    }).fail(function(response){
        $('#export-success-toast').html('Status: Failure').fadeOut(2000);
        console.log('fail')
    });
}

$(function() {
    $( document ).ready(function() {
        // Force the filter panel to hide by default, even if there are request.GET parameters
        let taskFilterPanel = $('#taskFilterPanel');
        taskFilterPanel.collapse('hide');
        taskFilterPanel.addClass('collapse');

        // In the crispyform content, the generated HTML has <div>s that contain the multiselect menus
        // just below their corresponding <label>s. Give them an id so we can show/hide them more easily.
        $('#div_id_border1.form-group > div').attr('id', "id_border1_content");
        // Ensure that the country select is always visible
        $('div#div_id_border0').show();
        // Hide the export toast
        $('#export-success-toast').hide();
        // If there's no country selection, then initially hide the submenu
	    let $select_border0 = $('select#id_border0');
	    if ($select_border0.val()) {
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
                // Not necessary with select2
                // $('select[name="border1"]').val('').trigger('change');
            });
        }

        // Initialize the selected tasks and counter
        let selected_tasks_count = document.getElementById('selected_tasks_count');
        let selected_tasks = document.getElementById('selected_tasks');
        if (selected_tasks_count) {
            const initial_selected_tasks_count = JSON.parse(selected_tasks_count.textContent);
            document.getElementById('reset-selections').hidden = (initial_selected_tasks_count === 0);
            document.getElementById('submit-id-update').disabled = (initial_selected_tasks_count === 0);
            document.getElementById('submit-id-bulk-sms').disabled = (initial_selected_tasks_count === 0);
            setExportButtonState(initial_selected_tasks_count);
        }
        if (selected_tasks) {
            const initial_selected_tasks = JSON.parse(selected_tasks.textContent);
            let pageSelections = 0;
            for (let t of initial_selected_tasks) {
                let cb = document.getElementById('id_tasks_' + t);
                if (cb != null) {
                    cb.checked = true;
                    pageSelections += 1;
                }
            }
            let per_page = Number(document.getElementById('per_page').textContent);
            if (pageSelections === per_page) {
                // If all records on this page were selected, check the checkbox in the header
                document.getElementById('bulk-select-all').checked = true;
            }
        }
    });

    // when panel is revealed. 'shown.bs.collapse' is a Bootstrap event
    // $('#taskFilterCard').on('shown.bs.collapse', function(e) {
        // $(this).find('.selectmultiple').chosen("destroy").chosen();
    // });

    // $('#bulkUpdateCard').on('shown.bs.collapse', function(e) {
        // $(this).find('.selectmultiple').chosen("destroy").chosen();
    // });

    $('#bulk-select-all').on('click', function(e) {
        $("input[name='bulk-tasks']").prop("checked", $(this).prop("checked") === true);
        selectTasks(null);
    });


    // the 'reset filter form' button
    $('#reset-filter-form').on("click", function (e) {
        // Reset all form entries. This is a bit hackish, but...
        // Reset all text and select inputs
        $('#filter-form input[type=text],select').val('')
        // Reset the select2 elements
        $('#id_border1').val('').trigger('change')
        $('#id_assignees').val('').trigger('change')
        $('#id_tags').val('').trigger('change')
    });

    // the 'reset bulk update form' button
    $('#reset-update-form').on("click", function (e) {
        // Reset all form entries. This is a bit hackish, but...
        // Reset all text and select inputs
        $('#tasks-bulk-update input[type=text],select').val('')
        $('#id_bulk-assignees').val('').trigger('change')
        $('#id_bulk-tags').val('').trigger('change')
    });
});

function selectTasks(cb) {
    // Extract the csrf token from the form
    let csrf = $('input[name="csrfmiddlewaretoken"]').attr('value')
    let filtered_data = {};
    // Add any checked Tasks to the filtered_data set
    $("input:checkbox[name='bulk-tasks']").each(function(){
        let task_id = $(this).val();
        filtered_data[task_id] = $(this)[0].checked;
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
        let tasks_selected_count = resp_data['tasks_selected_count'];
        if (tasks_selected_count > 0) {
            // If the total number selected > 0 was returned in the server response
            let tasks_name = 'Task';
            if (tasks_selected_count > 1) {
                tasks_name += 's'
            }
            // Update and show the 'Tasks Selected' UI
            document.getElementById('selected-tasks-count').innerHTML = tasks_name + ' Selected: ' + tasks_selected_count.toLocaleString();
            document.getElementById('reset-selections').hidden = false;
            document.getElementById('submit-id-update').disabled = false;
            document.getElementById('submit-id-bulk-sms').disabled = false;
        }
        else {
            // Update and hide the 'Tasks Selected' UI
            document.getElementById('selected-tasks-count').innerHTML = 'Tasks Selected: ' + tasks_selected_count.toLocaleString();
            document.getElementById('reset-selections').hidden = true;
            document.getElementById('submit-id-update').disabled = true;
        }
        setExportButtonState(tasks_selected_count);
    });
}

function selectAllTasks(cb) {
    $("input[name='bulk-tasks']").prop("checked", true);
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
        // Update and hide the 'Tasks Selected' UI
        document.getElementById('selected-tasks-count').innerHTML = 'Tasks Selected: ' + resp_data['tasks_selected_count'].toLocaleString();
        document.getElementById('reset-selections').hidden = false;
        document.getElementById('submit-id-update').disabled = false;
        document.getElementById('submit-id-bulk-sms').disabled = false;
        setExportButtonState(resp_data['tasks_selected_count']);
    });
}

function clearSelections(cb) {
    $("input[name='bulk-tasks']").prop("checked", false);
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
        // Update and hide the 'Tasks Selected' UI
        document.getElementById('selected-tasks-count').innerHTML = 'Tasks Selected: ' + resp_data['tasks_selected_count'].toLocaleString();
        document.getElementById('reset-selections').hidden = true;
        document.getElementById('submit-id-update').disabled = true;
        document.getElementById('submit-id-bulk-sms').disabled = true;
        setExportButtonState(resp_data['tasks_selected_count']);
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
    let form = $("form#tasks-export")
    let form_data = form.serializeArray();
    form_data.push({name: 'export-tasks', value: 'export-tasks'});
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

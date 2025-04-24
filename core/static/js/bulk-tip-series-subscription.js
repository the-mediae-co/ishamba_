function makeAjaxRequest(selections) {
    let form = django.jQuery('#bulktipseriessubscription_form');
    let token = form.find('input[name="csrfmiddlewaretoken"]');
    let csrf = token.val();
    let hrefs = window.document.location.href.split('/');
    hrefs.pop();  // Drop the trailing slash
    hrefs.pop();  // Drop the "add" suffix
    let url = hrefs.join('/') + "/count_customers/";
    let keys = Object.keys(selections);
    let filtered_data = keys.filter(function (key) {
        if (selections[key]) return key;
    });
    let ajax_dict = {
        type: 'post',
        url: url,
        headers: {'X-CSRFToken': csrf},
        data: {'selections': filtered_data},
    }
    let $current_request = django.jQuery.ajax(ajax_dict)
        .done(function (resp_data) {
            // Success
            // console.log("AJAX Success!");
            if (resp_data != null && Object.keys(resp_data).length !== 0) {
                // If data was returned in the response
                if ('count' in resp_data) {
                    if (django.jQuery('div#customer_count').length > 0) {
                        django.jQuery('div#customer_count').replaceWith("<div id='customer_count'><p>" + resp_data['count'].toLocaleString() + " Customers</p></div>");
                    } else {
                        django.jQuery("<div id='customer_count'><p>" + resp_data['count'].toLocaleString() + " Customers</p></div>").insertAfter('#bulktipseriessubscription_form > div > fieldset > div.form-row.field-categories');
                    }
                }
            }
        });
}

$( window ).on( "load", function() {
    let saveButton = document.getElementsByName("_save")[0];
    saveButton.value = "Subscribe";
    let addAnotherButton = document.getElementsByName("_addanother")[0];
    addAnotherButton.style.display = "none";
    let continueButton = document.getElementsByName("_continue")[0];
    continueButton.style.display = "none";
    window.currentSelections = {};
    django.jQuery('#id_category').on('select2:select', function (e) {
        console.log('Selected: ', e.params.data);
        let key = e.params.data['id'];
        window.currentSelections[key] = e.params.data['selected'];
        makeAjaxRequest(window.currentSelections)
    });
    django.jQuery('#id_category').on('select2:unselect', function (e) {
        console.log('UNselected: ', e.params.data);
        let key = e.params.data['id'];
        if(key in window.currentSelections) {
            delete window.currentSelections[key];
            makeAjaxRequest(window.currentSelections)
        }
    });
});

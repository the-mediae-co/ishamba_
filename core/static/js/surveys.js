$(function() {
    $( document ).ready(function() {
        // Hide the export toast
        $('#export-success-toast').hide();
    });
});

function setExportButtonState(selectedRecordsCount) {
    let emailButton = document.getElementById("export-button");
    if (emailButton) {
        let recordCountString = selectedRecordsCount.toLocaleString();
        emailButton.disabled = Number(selectedRecordsCount) === 0;
        emailButton.innerText = "Email " + recordCountString + " filtered records";
    }
}


function generateEmailReport(button) {
    let form = $("form#record-selection-form")
    let form_data = form.serializeArray();
    $('#export-success-toast').html('Status: Submitted...').show();
    $.post(
        '#',
        form_data
    ).done(function(data, status, xhr){
        $('#export-success-toast').html('Status: Success!<br/>Check your ' + data['user_email'] + ' email ').fadeOut(20000);
        console.log('Success! Sent report to: ' + data['user_email']);
    }).fail(function(response){
        $('#export-success-toast').html('Status: Failure').fadeOut(2000);
        console.log('fail')
    });
}

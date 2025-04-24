$('document').ready(function() {
    const $ = django.jQuery;
    function ShowHideCountriesList() {
        if ($('#id_all_countries').prop('checked')) {
            $('div.form-row.field-countries').hide(400);
        }
        else {
            $('div.form-row.field-countries').show(400);
        }
    }
    function ChangeSenderOptions() {
        // Build an array of selected countries
        let countries = $('#id_countries :selected').map(function () {
            return $(this).text();
        }).get();
        let all_countries = $('#id_all_countries').prop('checked')
        let needs_selection = false;
        // Set sender menu items disabled state based on the selected countries
        $('#id_sender option').each(function () {
            if (all_countries || $(this)[0].label.search(new RegExp(countries.join('|'))) >= 0) {
                $(this).prop('disabled', false);
            }
            else {
                if ($(this).prop("selected")) {
                    needs_selection = true;
                }
                $(this).prop('disabled', true);
            }
        });
        // If we disabled the selected item, select a new valid one
        if (needs_selection) {
            $('#id_sender option:not([disabled]):first').prop("selected", true);
        }
    }
    $(document).on('click', '#id_all_countries', function() {
        ShowHideCountriesList();
        ChangeSenderOptions();
    });
    $('select#id_countries').change(function() {
        ChangeSenderOptions();
    });
    ShowHideCountriesList();
    ChangeSenderOptions();
});

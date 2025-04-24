function findPaginationBreak(chunk, break_on = '\n') {
    // Find the best break point in a given chunk, giving priority to the break_on string,
    // then to any space.
    // Returns the offset within the chunk, or -1 if no good break could be found.
    // This replicates the logic used on the server side to paginate messages.

    const MIN_MESSAGE_LEN = 2;
    let offset = chunk.lastIndexOf(break_on);
    if (offset < MIN_MESSAGE_LEN)
        offset = chunk.lastIndexOf(' ');
    if (offset < MIN_MESSAGE_LEN)
        offset = -1;

    return offset
}

function splitTextIntoPages(text, break_on = '\n') {
    // Packs a given string into the fewest number of messages,
    // using the same algorithm that the server uses.
    // Args:
    //      text: str
    //      break_on: char use if the message needs to be split
    // Returns:
    //      A list of strings representing the individual messages to be sent

    const limit = 160 - 6; // max sms length minus 6 characters to indicate pagination
    let lenTxt = text.length;

    // The GSM extended set characters take one additional character slot each
    const gsmRegex = new RegExp(window.gsmExtendedSetRegex, 'g');
    let gsmExtendedCount = (text.match(gsmRegex) || []).length;

    if (lenTxt + gsmExtendedCount <= limit) {
        // Should never happen since we only call this method when there are multiple pages.
        return [text.replace(break_on, ' ')];
    }

    let messages = [];
    let offset = 0;
    while (offset < lenTxt) {
        let end = offset + limit;
        let chunk = text.substring(offset, end);
        let chunkRegexCount = (chunk.match(gsmRegex) || []).length;
        // If there's a GSM Extended set character in the chunk, shorten
        // the chunk length because they take extra space in encoding.
        if (chunkRegexCount) {
            end -= chunkRegexCount;
            chunk = text.substring(offset, end);
        }
        let lastBreak = findPaginationBreak(chunk, break_on);
        if ((lastBreak != -1) && (end < lenTxt)) {
            // Shrink chunk, replace break, and move offset
            chunk = chunk.substring(0, lastBreak);
            offset += lastBreak + 1;
        } else {
            offset += limit;
        }
        chunk = chunk.replace(break_on, ' ')
        messages.push(chunk.trim())
    }

    let pages = [];
    let total = messages.length;
    messages.forEach(function (message, page) {
        let paginationString = ' (' + (page + 1) + '/' + total + ')';
        pages.push(message + paginationString);
    });
    messages = pages;

    return messages
}

function configureSenderMenus() {
    if (! window.countries) {
        window.countries = eval($('#id_countries').val());
    }

    for(let country_name of window.countries) {
        let id_sender_options = '#id_sender_' + country_name + ' option';
        let needs_selection = false;
        let options = $(id_sender_options)
        // Set sender menu items disabled state based on the selected countries
        $.each(options, function(index, value) {
            if (value.label.search(country_name) >= 0) {
                value.disabled = false;
            }
            else {
                if (value.selected) {
                    needs_selection = true;
                }
                value.disabled = true;
            }
        });
        // If we disabled the selected item, select a new valid one
        if (needs_selection) {
            $(id_sender_options + ':not([disabled]):first').prop("selected", true);
        }
    }
}

function evalFormState() {
    let txt = $('#id_text').val();
    if (! window.gsmCharset) {
        window.gsmCharset = $('#id_gsm_charset').val();
    }
    if (! window.gsmExtendedSetRegex) {
        window.gsmExtendedSetRegex = $('#id_gsm_charset').val();
    }

    let remaining = 160 - txt.length;
    let gsmExtendedCount = (txt.match(new RegExp(window.gsmExtendedSetRegex, 'g')) || []).length;
    remaining -= gsmExtendedCount;
    let invalidChars = txt.split(new RegExp('[' + window.gsmCharset.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ']')).join('');
    let checkbox = $('#id-enable-multiple-pages');
    let enableMultiplePages = checkbox.prop('checked') || false;
    let disableSubmit = false;
    if (invalidChars.length > 0) {
        let plural = ''
        if (invalidChars.length > 1) {
            plural = 's'
        }
        $('#illegal-character').text('ERROR: Illegal GSM character' + plural + ' detected: ' + invalidChars);
        disableSubmit = true;
    } else {
        $('#illegal-character').text('');
    }
    if (remaining >= 0) {
        $('#allow-multiple-pages').text('')
        if (checkbox.length) {
            checkbox.remove();
        }
        enableMultiplePages = false;
    }
    else if (!enableMultiplePages && remaining < 0) {
        disableSubmit = true;
        $('#allow-multiple-pages').text(
            'Your message is more than 160 characters and will require multiple messages. Approve? '
        ).append(
            '<input type="checkbox" id="id-enable-multiple-pages" ' +
            'name="enable-multiple-pages" onclick="evalFormState()"> ' +
            '<label for="enable-multiple-pages">Yes</label>'
        );
    }
    if (enableMultiplePages) {
        let pages = splitTextIntoPages(txt);
        let uiString = '<span>' + pages.length + ' messages ( ' + txt.length + ' characters )</span><br><small><ul>';
        pages.forEach(function (page, index) {
            uiString += '<li style="list-style-type: decimal;">\“' + page + '\”</li>';
        });
        uiString += '</ul></small>';
        $('#counter').html(uiString);
    } else {
        $('#counter').text('One message: ' + remaining + ' characters remaining');
    }
    $('#submit-id-submit').prop('disabled', disableSubmit);
}

$('document').ready(function() {
    // gsm extended set characters consume one additional character in encoding
    window.gsmExtendedSetRegex = /[\^\{\}\\\|\[\]~€\f]/;
    window.gsmCharset = $('#id_gsm_charset').val();
    window.countries = eval($('#id_countries').val());
    $(document).on('keyup', '#id_text', function() {
        evalFormState();
    });
    configureSenderMenus();
    $('#id_text').keyup();
});

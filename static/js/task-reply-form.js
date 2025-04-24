$(function(){
    var reply_form = $('#reply-form'),
        reply_form_error = $('#reply-form-error');

    reply_form.find('[data-dismiss]').click(function(e){
        e.preventDefault();
        reply_form_error.addClass('hidden');
    })

    reply_form.on('submit', function(e){
        e.preventDefault();
        let form = $(this);

        reply_form.find('.controls').children().addClass('disabled');

        $.post(
            form.attr('action'),
            form.serialize()
        ).done(function(data, status, xhr){
            if(data.success){
                location.reload()
            }else{
                reply_form.find('.form-body').html(data);
                $('#id_text').keyup();
            }
        }).fail(function(response){
            reply_form_error.html('There was an error, please try again shortly.');
            reply_form_error.removeClass('hidden');
        }).always(function(){
            reply_form.find('.controls').children().removeClass('disabled');
        });
    });
});

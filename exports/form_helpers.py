from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, HTML, Row, Submit, Div


class CustomerExportFormHelper(FormHelper):
    form_tag = False
    disable_csrf = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.layout = Layout(
            Row(
                Div('tasks__created__date__gte', css_class="col-md-6 js-date-picker"),
                Div('tasks__created__date__lt', css_class="col-md-6 js-date-picker")
            ),

            Row(
                Div('tasks__tags__name__in', css_class="col-md-6 remote-tags js-remote-tags"),
            ),

            Row(
                Div('postal_code', css_class="col-md-6"),
                Div('border0_id', 'border1_id', css_class="col-md-6"),
            ),

            Row(
                Div('incomplete_records', css_class="col-md-6"),
            ),

            Submit('submit', 'Export', css_class='mod-export')
        )


class FieldSelectionFormHelper(FormHelper):
    form_tag = False
    disable_csrf = True

    layout = Layout(
        HTML('<p>Fields to include in the export</p>'),
        'fields'
    )


class IncomingSMSExportFormHelper(FormHelper):
    form_tag = False
    form_class = 'col s12'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.layout = Layout(
            Row(
                Div('at__date__gte', css_class="col-md-4 js-date-picker"),
                Div('at__date__lt', css_class="col-md-4 js-date-picker")),
            Row(
                Div('task__tags__name__in', css_class="col-md-4 remote-tags js-remote-tags")
            ),

            Row(
                Div('customer__border1_id', 'customer__border0_id', css_class="col-md-4 input-field")
            ),

            Submit('submit', 'Export', css_class='mod-export')
        )

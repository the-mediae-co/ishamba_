from django import forms

from .form_helpers import FieldSelectionFormHelper


class FieldSelectionForm(forms.Form):

    fields = forms.MultipleChoiceField(choices=[],
                                       widget=forms.CheckboxSelectMultiple(),
                                       label='')

    helper = FieldSelectionFormHelper()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fields'].choices = self.EXPORTED_FIELD_CHOICES


class CustomerFieldSelectionForm(FieldSelectionForm):

    EXPORTED_FIELD_CHOICES = (
        ('name', 'Name'),
        ('sex', 'Sex'),
        ('dob', 'Date of birth'),
        ('phones__number', 'Phone number'),
        ('county__name', 'County'),
        ('postal_address', 'Postal address'),
        ('postal_code', 'Postal code'),
    )


class IncomingSMSFieldSelectionForm(FieldSelectionForm):

    EXPORTED_FIELD_CHOICES = (
        ('task__id', 'Task ID'),
        ('at', 'Time received'),
        ('sender', 'Phone number'),
        ('text', 'Message text'),
        ('customer__sex', 'Customer sex'),
    )

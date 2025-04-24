from django import forms
from django.forms.models import ModelChoiceIterator

from core.forms import SelectWithData


class TipSeriesChoiceIterator(ModelChoiceIterator):

    def choice(self, obj):
        """ Return tuple of value, label and option attributes """
        value, label = super().choice(obj)
        attrs = {}
        return (value, obj.name, attrs)


class TipSeriesChoiceField(forms.ModelChoiceField):

    widget = SelectWithData

    @property
    def choices(self):
        """ Return generator that yields each option for the field """
        # We override the default choices to inject data attributes
        return TipSeriesChoiceIterator(self)

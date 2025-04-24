from django import forms
from django.forms.models import ModelChoiceIterator

from core.forms import SelectWithData


class CommodityChoiceIterator(ModelChoiceIterator):

    def choice(self, obj):
        """ Return tuple of value, label and option attributes """
        value, label = super().choice(obj)
        attrs = {}
        if obj.gets_market_prices:
            attrs['data-prices'] = 'true'
        if obj.is_event_based:
            attrs['data-event-based'] = 'true'
        return (value, obj.name, attrs)


class CommodityChoiceField(forms.ModelChoiceField):

    widget = SelectWithData

    @property
    def choices(self):
        """ Return generator that yields each option for the field """
        # We override the default choices to inject data attributes
        return CommodityChoiceIterator(self)

from django import forms


class BaseDeliveryReportForm(forms.Form):
    """
    Base form for accepting delivery report POST requests from SMS gateways as
    a callback.
    """
    FIELD_NAME_MAPPING = {
    }

    mno_message_id = forms.CharField(max_length=100, required=False)
    status = forms.CharField(max_length=100)

    def add_prefix(self, field_name):
        """
        Looks up the field name in the `FIELD_NAME_MAPPING` dict and translates
        the field name if required.
        """
        field_name = self.FIELD_NAME_MAPPING.get(field_name, field_name)
        return super(BaseDeliveryReportForm, self).add_prefix(field_name)

from datetime import timezone
from dateutil import parser as dateparser

from django import forms

from gateways.forms import BaseDeliveryReportForm
from sms.forms import BaseIncomingSMSForm


class ATIncomingSMSForm(BaseIncomingSMSForm):
    """
    Incoming SMS form with field mappings overridden to match the
    AfricasTalking SMS callback POST request.
    """

    FIELD_NAME_MAPPING = {
        'sender': 'from',
        'recipient': 'to',
        'at': 'date',
        'gateway_id': 'id'
    }
    at = forms.CharField(max_length=100)

    def clean_at(self):
        """
        AfricasTalking send us timestamps in UTC (ISO 8601 format),
        however, Django presumes that timezones are in localtime unless told
        otherwise.

        25-March-2021: New format: '2021-03-25T11:52:22.972Z'
        """
        value = self.cleaned_data['at']
        dt = dateparser.isoparse(value)  # dateparser is more flexible and forgiving than datetime.strptime()
        dt = dt.replace(tzinfo=timezone.utc)

        return dt


class ATDeliveryReportForm(BaseDeliveryReportForm):
    FIELD_NAME_MAPPING = {
        'mno_message_id': 'id',
        'failure_reason': 'failureReason',
    }

    failure_reason = forms.CharField(max_length=100, required=False)

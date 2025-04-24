from django.db.models import CharField

from gateways.gateways import SMSGateway
from .validators import GSMCharacterSetValidator


class SMSCharField(CharField):
    """
    A CharField subclass that sets max_length to the max SMS length multiplied
    by the max number of pages that we allow per SMS. NOTE that this is a bit
    simplistic since the GSM extended set characters add additional length
    in encoding. However, the ajax UI and gateway sending methods check for this.
    """
    description = (f"A {SMSGateway.MESSAGE_MAX_LEN * SMSGateway.MAX_SMS_PER_MESSAGE}-character "
                   "charfield that accepts only GSM-character set-friendly characters.")
    default_validators = [GSMCharacterSetValidator]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = SMSGateway.MESSAGE_MAX_LEN * SMSGateway.MAX_SMS_PER_MESSAGE
        super().__init__(*args, **kwargs)

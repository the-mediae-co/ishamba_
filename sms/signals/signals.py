from django.dispatch import Signal

# sms_sent = Signal(providing_args=["sms", "recipient_ids"])
sms_sent = Signal()
sms_received = Signal()

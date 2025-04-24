from logging import getLogger

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now

from actstream import action
from actstream.models import Action
from customers.constants import JOIN_METHODS
from gateways import gateways
from gateways.signals import delivery_report_received

from core import constants as core_constants
from customers.models import Customer, get_or_create_customer_by_phone

from ..models import (OutgoingSMS, IncomingSMS, SMSResponseTemplate)
from ..tasks import record_delivery_report_task
from .signals import sms_sent, sms_received

logger = getLogger(__name__)


@receiver(sms_received)
def process_incoming_sms(sender, **kwargs):
    """
    This signal is triggered when receiving an incoming SMS in the BaseIncomingSMSView.post() method
    """
    msg: IncomingSMS = kwargs['instance']  # this should probably be an arg...

    msg.customer, msg.customer_created = get_or_create_customer_by_phone(msg.sender, JOIN_METHODS.SMS)
    # Note that if a customer is created as a result of this incoming msg,
    # the customer's join_method is also set at the end of the IncomingSMS.create_vanilla_task() method.
    msg.gateway = gateways.AT
    msg.save()

    msg.process()


@receiver(post_save, sender=IncomingSMS)
def handle_incoming_sms(sender, instance, created, **kwargs):
    if not created:
        return

    action.send(instance.customer, verb=core_constants.CUSTOMER_SENT_SMS,
                action_object=instance, timestamp=instance.at)


# outgoing_sms_sent dispatch_uid is used only for testing purposes
@receiver(sms_sent, sender=OutgoingSMS, dispatch_uid="outgoing_sms_sent")
def handle_outgoing_sms(sender, sms, recipient_ids, **kwargs):
    time_sent = sms.time_sent or now()

    action_args = {
        'actor_content_type': ContentType.objects.get_for_model(Customer),
        'verb': str(core_constants.CUSTOMER_RECIEVED_SMS),
        'public': True,
        'action_object_object_id': sms.id,
        'action_object_content_type': ContentType.objects.get_for_model(sms),
    }

    customer_ids = (sms.get_extant_recipients()
                       .filter(recipient_id__in=recipient_ids)
                       .values_list('recipient_id', flat=True))

    action_args['timestamp'] = time_sent

    actions = []

    for customer_id in customer_ids:
        args = action_args.copy()
        args['actor_object_id'] = customer_id
        actions.append(Action(**args))

    Action.objects.bulk_create(actions)


@receiver(delivery_report_received, dispatch_uid="update_sms_receipient_status")
def record_delivery_report(sender, mno_message_id=None, status='', failure_reason='', **kwargs):
    if not mno_message_id:
        logger.error('Invalid delivery report received')
        return
    client = connection.tenant.schema_name
    # We delay the task by 10s to processing reports for messages that have not been saved yet
    record_delivery_report_task.apply_async(args=(client, mno_message_id),
                                            kwargs={'status': status, 'failure_reason': failure_reason},
                                            countdown=10)


# This works, but adds overhead on every save, and should be unnecessary since the only
# method of changing a SMSResponseTemplate is via the admin interface, which implements
# an appropriate save_related() method that does the same thing.

# @receiver(post_save, sender=SMSResponseTemplate)
# def handle_sms_response_template_save(sender, instance, created, **kwargs):
#     # If this template applies to all countries, remove any individual country selections
#     if instance.all_countries:
#         instance.countries.clear()

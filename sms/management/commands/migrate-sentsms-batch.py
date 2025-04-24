import argparse
import time
import hashlib
import json

from django.core.management.base import BaseCommand
from django.db import connection
from django.contrib.contenttypes.models import ContentType

from django_tenants.management.commands import InteractiveTenantOption

from sms.models.outgoing import OutgoingSMS, SMSRecipient, SentSMS

import logging

logger = logging.getLogger(__name__)

# A flag controlling whether to do the pre-flight uniqueness check for debugging
pre_flight_check_uniqueness = True
recipient_message_page_ids = {}

chunk_size = 5000

failure_reasons = {
    401: 'RiskHold',
    402: 'InvalidSenderId',
    403: 'InvalidPhoneNumber',
    404: 'UnsupportedNumberType',
    405: 'InsufficientBalance',
    406: 'UserInBlackList',
    407: 'CouldNotRoute',
    500: 'InternalServerError',
    501: 'GatewayError',
    502: 'RejectedByGateway',
}


class Command(BaseCommand, InteractiveTenantOption):
    help = 'Migrate a batch of SentSMS messages to OutgoingSMS'

    # Usage: ./manage.py migrate-sentsms-batch -t -v1 -n <<batch_size>> -s ishamba

    def add_arguments(self, parser: argparse.ArgumentParser):

        parser.add_argument("-n", "--num", dest="conversion_size", required=True,
                            type=int, default=0, help="number of records to convert")
        parser.add_argument("-s", "--schema", default="ishamba", dest="schema_name", help="tenant schema")
        parser.add_argument("-t", "--test", dest="test_run", action='store_true',
                            help="test run: no sms messages are sent")
        # parser.add_argument("-v", "--verbose", action="count", default=0,
        #                     help="increase output verbosity")

    def create_one_sms_recipient(self, sentsms, outgoingsms, outgoingsms_type,
                                 gateway_msg_id: str = None, delivery_status: str = "Success",
                                 failure_reason: str = "", page_index: int = 1, extra: dict = None):
        # If a gateway hash was not provided, make one up
        # We start it with '???' to help identify such messages as not coming from a gateway
        if not gateway_msg_id or gateway_msg_id == 'None':
            msg_text = sentsms.text or ""
            msg_hash = hashlib.sha1(msg_text.encode() +
                                    str(sentsms.customer.id).encode() +
                                    json.dumps(sentsms.time_sent, default=str).encode() +
                                    str(page_index).encode() +
                                    str(sentsms.pk).encode())
            gateway_msg_id = '???' + msg_hash.hexdigest()

        if not extra:
            extra = {}

        new_obj = SMSRecipient(
            recipient=sentsms.customer,
            # point the ForeignKey to the new obj
            message=outgoingsms,
            # Retain the old style GenericRelation fields for now, so the code still works as we transition
            content_type=outgoingsms_type,
            object_id=outgoingsms.id,
            gateway_msg_id=gateway_msg_id,
            delivery_status=delivery_status,
            failure_reason=failure_reason,
            page_index=page_index,
            extra=extra,
            created=sentsms.created,
            creator_id=sentsms.creator_id,
            last_updated=sentsms.last_updated,
            last_editor_id=sentsms.last_editor_id,
        )
        # A bit of a hack to temporarily disable the auto_now_add and auto_now fields without creating another migration
        auto_field = next(iter([x for x in new_obj._meta.fields if x.name == 'created']), None)
        auto_field.auto_now_add = False
        auto_field = next(iter([x for x in new_obj._meta.fields if x.name == 'last_updated']), None)
        auto_field.auto_now = False

        # Unique constraint pre-flight checking
        if pre_flight_check_uniqueness:
            recipient_message_page_str = f"{sentsms.customer.id}-{outgoingsms.id}-{page_index}"
            if recipient_message_page_ids.get(recipient_message_page_str):
                print(f"Duplicate detected: {recipient_message_page_str}")
                logger.debug(f"Duplicate detected: {recipient_message_page_str}")
                raise ValueError
            else:
                recipient_message_page_ids[recipient_message_page_str] = True

        return new_obj

    def parse_extra_pages(self, sentsms, outgoingsms, outgoingsms_type):
        smsrecipient_list = []
        if not sentsms.extra:  # None or {}
            # Just create one SMSRecipient object for the main recipient information
            # using fake data for the unknown fields
            new_obj = self.create_one_sms_recipient(sentsms, outgoingsms, outgoingsms_type)

            # Add to the list of the objects to bulk_create below
            smsrecipient_list.append(new_obj)
        else:
            # Create one SMSRecipient for each page of the sent message
            pages = sentsms.extra.get('pages')
            for page_index in pages.keys():
                details = pages.get(str(page_index))
                if len(details) == 0:
                    continue
                if isinstance(details, list) and len(details) > 0:
                    details = details[0]
                if page_index == '1' and not details:
                    # Just create one SMSRecipient object for the main recipient information
                    # using fake data for the unknown fields
                    new_obj = self.create_one_sms_recipient(sentsms, outgoingsms, outgoingsms_type)

                    # Add to the list of the objects to bulk_create below
                    smsrecipient_list.append(new_obj)

                    continue  # If there's no page for this fragment, create the SMSRecipient and move on

                gateway_msg_id = details.get('messageId', None)
                delivery_status = details.get('status', 'Success')  # If not recorded, assume it was successful
                status_code = details.get('statusCode', 100)
                failure_reason = failure_reasons.get(status_code, "")

                new_obj = self.create_one_sms_recipient(sentsms, outgoingsms, outgoingsms_type,
                                                        gateway_msg_id, delivery_status,
                                                        failure_reason, page_index, details)

                # Keep a list of the objects to bulk_create below
                smsrecipient_list.append(new_obj)

        return smsrecipient_list

    def handle(self, *args, **options):

        # Track performance for summary report
        tic = time.perf_counter()

        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)

        conversion_size = options['conversion_size']
        verbosity = options['verbosity']
        test_run = options['test_run']

        outgoingsms_type = ContentType.objects.get_for_model(OutgoingSMS)

        outgoingsms_chunk = []
        sentsms_chunk = []
        converted_sentsms_ids = []
        smsrecipient_chunk = []
        msg_count = 0
        recipients_count = 0

        tic = time.perf_counter()
        # Loading all objects takes too much memory so we use a db iterator and chunk the creation.
        # https://docs.djangoproject.com/en/2.2/ref/models/querysets/#iterator
        # Migrate most recent messages first
        for sentsms in SentSMS.objects.order_by('-pk').iterator(chunk_size=chunk_size):
            extra = sentsms.extra or {}
            outgoingsms = OutgoingSMS(
                text=sentsms.text,
                time_sent=sentsms.time_sent,
                sent_by_id=sentsms.creator_id,
                message_type='one',
                incoming_sms=None,
                # sms_recipient=None,  # we will be deleting this field in a later migration
                extra=extra,  # The 'extra' will also be added to each SMSRecipient object
                created=sentsms.created,
                creator_id=sentsms.creator_id,
                last_updated=sentsms.last_updated,
                last_editor_id=sentsms.last_editor_id,
            )

            # A bit of a hack to temporarily disable the auto_now_add and auto_now fields without creating another migration
            auto_field = next(iter([x for x in outgoingsms._meta.fields if x.name == 'created']), None)
            auto_field.auto_now_add = False
            auto_field = next(iter([x for x in outgoingsms._meta.fields if x.name == 'last_updated']), None)
            auto_field.auto_now = False

            # Keep lists of the objects to bulk_create below
            outgoingsms_chunk.append(outgoingsms)
            sentsms_chunk.append(sentsms)
            converted_sentsms_ids.append(sentsms.id)

            msg_count += 1
            if msg_count % chunk_size == 0:
                # Commit a batch of new messages to the DB at once for efficiency.
                # Note that OutgoingSMS.save() auto-updates fields in a way that would
                # cause us problems. However, bulk_create bypasses save() so this works.
                outgoings = OutgoingSMS.objects.bulk_create(outgoingsms_chunk)
                # Create corresponding SMSRecipients for the new OutgoingSMS objects
                for sent, out in zip(sentsms_chunk, outgoings):
                    new_recipients = self.parse_extra_pages(sent, out, outgoingsms_type)
                    smsrecipient_chunk.extend(new_recipients)
                    recipients_count += len(new_recipients)

                # Delete the converted SentSMS messages
                SentSMS.objects.filter(id__in=converted_sentsms_ids).delete()

                # Free up memory
                outgoingsms_chunk = []
                converted_sentsms_ids = []
                sentsms_chunk = []

                SMSRecipient.objects.bulk_create(smsrecipient_chunk)
                smsrecipient_chunk = []

                toc1 = time.perf_counter()
                if verbosity:
                    logger.debug(f"{msg_count} SentSMS and {recipients_count} "
                                 f"SMSRecipient objects converted in {toc1 - tic:0.1f} seconds. "
                                 f"{msg_count / (toc1 - tic):0.2f}/s")

            if msg_count >= conversion_size:
                break

        # Commit the final batch
        outgoings = OutgoingSMS.objects.bulk_create(outgoingsms_chunk)
        for sent, out in zip(sentsms_chunk, outgoings):
            new_recipients = self.parse_extra_pages(sent, out, outgoingsms_type)
            smsrecipient_chunk.extend(new_recipients)
            recipients_count += len(new_recipients)

        # Delete the converted SentSMS messages
        SentSMS.objects.filter(id__in=converted_sentsms_ids).delete()

        # Free up memory
        outgoingsms_chunk = []
        converted_sentsms_ids = []
        sentsms_chunk = []
        new_recipients = None
        SMSRecipient.objects.bulk_create(smsrecipient_chunk)

        # Free up memory
        smsrecipient_chunk = None

        # Now delete any OutgoingSMS messages of this type that have no recipients.
        OutgoingSMS.objects.filter(recipients__isnull=True, message_type='one').delete()

        if verbosity:
            toc2 = time.perf_counter()
            logger.debug(f"{msg_count} SentSMS and {recipients_count} "
                         f"SMSRecipient objects converted in {toc2 - tic:0.1f} seconds. "
                         f"{msg_count / (toc2 - tic):0.2f}/s")

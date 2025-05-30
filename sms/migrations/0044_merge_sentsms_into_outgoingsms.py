# Generated by Django 2.2.24 on 2021-07-15 15:06
import json
import hashlib
import time

from django.db import migrations
from django.conf import settings

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


def create_one_sms_recipient(SMSRecipient, sentsms, outgoingsms, outgoingsms_type,
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


def parse_extra_pages(SMSRecipient, sentsms, outgoingsms, outgoingsms_type):
    smsrecipient_list = []
    if not sentsms.extra:  # None or {}
        # Just create one SMSRecipient object for the main recipient information
        # using fake data for the unknown fields
        new_obj = create_one_sms_recipient(SMSRecipient, sentsms, outgoingsms, outgoingsms_type)

        # Add to the list of the objects to bulk_create below
        smsrecipient_list.append(new_obj)
    else:
        # Create one SMSRecipient for each page of the sent message
        pages = sentsms.extra.get('pages')
        for page_index in pages.keys():
            details = pages.get(str(page_index))
            if isinstance(details, list) and len(details) > 0:
                details = details[0]
            if page_index == '1' and not details:
                # Just create one SMSRecipient object for the main recipient information
                # using fake data for the unknown fields
                new_obj = create_one_sms_recipient(SMSRecipient, sentsms, outgoingsms, outgoingsms_type)

                # Add to the list of the objects to bulk_create below
                smsrecipient_list.append(new_obj)

                continue  # If there's no page for this fragment, create the SMSRecipient and move on

            gateway_msg_id = details.get('messageId', None)
            delivery_status = details.get('status', 'Success')  # If not recorded, assume it was successful
            status_code = details.get('statusCode', 100)
            failure_reason = failure_reasons.get(status_code, "")

            new_obj = create_one_sms_recipient(SMSRecipient, sentsms, outgoingsms, outgoingsms_type,
                                               gateway_msg_id, delivery_status,
                                               failure_reason, page_index, details)

            # Keep a list of the objects to bulk_create below
            smsrecipient_list.append(new_obj)

    return smsrecipient_list


def consolidate_sms_messages(apps, schema_editor):
    """
    Consolidate all SentSMS instances into OutgoingSMS instances.
    """

    logger.setLevel(logging.DEBUG)
    settings.LOGGING['loggers']['django'] = {'level': 'DEBUG', 'handlers': ['console']}

    if schema_editor.connection.schema_name == 'ishamba':
        logger.warning("Due to the size of the ishamba data, this migration is too slow to "
                       "complete as one batch. The migration index has been advanced "
                       "but to convert the data, run the sms management command instead.")

        return True

    db_alias = schema_editor.connection.alias

    SMSRecipient = apps.get_model("sms", "SMSRecipient")  # NOQA
    OutgoingSMS = apps.get_model("sms", "OutgoingSMS")  # NOQA
    ContentType = apps.get_model("contenttypes", "ContentType")  # NOQA
    SentSMS = apps.get_model("sms", "SentSMS")  # NOQA

    outgoingsms_type = ContentType.objects.get_for_model(OutgoingSMS)

    outgoingsms_chunk = []
    sentsms_chunk = []
    smsrecipient_chunk = []
    msg_count = 0
    recipients_count = 0

    tic = time.perf_counter()
    # Loading all objects takes too much memory so we use a db iterator and chunk the creation.
    # https://docs.djangoproject.com/en/2.2/ref/models/querysets/#iterator
    for sentsms in SentSMS.objects.using(db_alias).order_by('-pk').iterator(chunk_size=chunk_size):
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

        # Keep lists of the objects to bulk_create below
        outgoingsms_chunk.append(outgoingsms)
        sentsms_chunk.append(sentsms)

        msg_count += 1
        if msg_count % chunk_size == 0:
            # Commit a batch of new messages to the DB at once for efficiency.
            # Note that OutgoingSMS.save() auto-updates fields in a way that would
            # cause us problems. However, bulk_create bypasses save() so this works.
            outgoings = OutgoingSMS.objects.using(db_alias).bulk_create(outgoingsms_chunk)
            # Create corresponding SMSRecipients for the new OutgoingSMS objects
            for sent, out in zip(sentsms_chunk, outgoings):
                new_recipients = parse_extra_pages(SMSRecipient, sent, out, outgoingsms_type)
                smsrecipient_chunk.extend(new_recipients)
                recipients_count += len(new_recipients)

            # Free up memory
            outgoingsms_chunk = []
            sentsms_chunk = []

            SMSRecipient.objects.using(db_alias).bulk_create(smsrecipient_chunk)
            smsrecipient_chunk = []
            toc1 = time.perf_counter()
            logger.debug(f"{msg_count} SentSMS and {recipients_count} "
                         f"SMSRecipient objects converted in {toc1 - tic:0.1f} seconds."
                         f"{msg_count / (toc1 - tic):0.2f}")

    # Commit the final batch
    outgoings = OutgoingSMS.objects.using(db_alias).bulk_create(outgoingsms_chunk)
    for sent, out in zip(sentsms_chunk, outgoings):
        new_recipients = parse_extra_pages(SMSRecipient, sent, out, outgoingsms_type)
        smsrecipient_chunk.extend(new_recipients)
        recipients_count += len(new_recipients)

    # Free up memory
    outgoingsms_chunk = []
    sentsms_chunk = []

    SMSRecipient.objects.using(db_alias).bulk_create(smsrecipient_chunk)

    # Free up memory
    smsrecipient_chunk = None

    # Now delete any OutgoingSMS messages of this type that have no recipients.
    OutgoingSMS.objects.using(db_alias).filter(recipients__isnull=True, message_type='one').delete()

    SentSMS.objects.using(db_alias).all().delete()  # Once converted, delete the originals

    toc2 = time.perf_counter()
    logger.debug(f"{msg_count} SentSMS and {recipients_count} "
                 f"SMSRecipient objects converted in {toc2 - tic:0.1f} seconds."
                 f"{msg_count / (toc2 - tic):0.2f}")


def reverse_sms_consolidation(apps, schema_editor):
    """
    De-Consolidate all OutgoingSMS instances back into SentSMS instances.
    """

    logger.setLevel(logging.DEBUG)
    settings.LOGGING['loggers']['django'] = {'level': 'DEBUG', 'handlers': ['console']}

    if schema_editor.connection.schema_name == 'ishamba':
        logger.warning("Due to the size of the ishamba data, this migration is too slow to "
                       "complete as one batch. The migration index has been moved back "
                       "but to convert the data, run the sms management command instead.")

        return True

    db_alias = schema_editor.connection.alias
    ContentType = apps.get_model("contenttypes", "ContentType")  # NOQA
    SMSRecipient = apps.get_model("sms", "SMSRecipient")  # NOQA
    OutgoingSMS = apps.get_model("sms", "OutgoingSMS")  # NOQA
    SentSMS = apps.get_model("sms", "SentSMS")  # NOQA

    # An array to hold newly created messages
    sentsms_chunk = []
    msg_count = 0

    tic = time.perf_counter()

    # Find all OutgoingSMS objects that were consolidated from SentSMS's
    # Loading all objects takes too much memory so we use a db iterator and chunk the creation.
    # https://docs.djangoproject.com/en/2.2/ref/models/querysets/#iterator
    for out in OutgoingSMS.objects.using(db_alias) \
        .filter(message_type='one').order_by('pk').iterator(chunk_size=chunk_size):

        # Recreate the 'extra' dictionary
        recipients = out.recipients.order_by('page_index')
        extra = {}
        customer = recipients.first().recipient  # SentSMS only supported ane recipient so assume the first is correct
        customer_id = customer.pk if customer else None
        page_index = 0
        pages = {}
        # We make the assumption that OutgoingSMS messages of type 'one' have only
        # one recipient. If there are multiple SMSRecipient objects, it is due to
        # pagination of the message text, splitting it into multiple segments.
        for recipient in recipients:
            page_index += 1
            details = recipient.extra
            pages.update({str(page_index): [details]})
        if pages:
            extra = {'pages': pages, 'total_pages': page_index}

        # Create a new object to hold the OutgoingSMS content
        new_sent = SentSMS(
            text=out.text,
            customer_id=customer_id,
            extra=extra,
            created=out.created,
            creator_id=out.creator_id,
            last_updated=out.last_updated,
            last_editor_id=out.last_editor_id,
            time_sent=out.time_sent,
        )
        # A bit of a hack to temporarily disable the auto_now_add field without creating another migration
        auto_field = next(iter([x for x in new_sent._meta.fields if x.name == 'time_sent']), None)
        auto_field.auto_now_add = False

        sentsms_chunk.append(new_sent)

        msg_count += 1
        if msg_count % chunk_size == 0:
            # Commit a batch of new messages to the DB at once for efficiency.
            SentSMS.objects.using(db_alias).bulk_create(sentsms_chunk)

            # Free up memory
            sentsms_chunk = []

            toc1 = time.perf_counter()
            logger.debug(f"{msg_count} SentSMS "
                         f"converted in {toc1 - tic:0.1f} seconds. "
                         f"{msg_count / (toc1 - tic):0.2f}/s")

    # Commit the final batch
    SentSMS.objects.using(db_alias).bulk_create(sentsms_chunk)

    # Free up memory
    sentsms_chunk = None

    OutgoingSMS.objects.using(db_alias).filter(message_type='one').delete()  # Once converted, delete the originals.

    toc2 = time.perf_counter()
    logger.debug(f"{msg_count} SentSMS "
                 f"objects converted in {toc2 - tic:0.1f} seconds. "
                 f"{msg_count / (toc2 - tic):0.2f}/s")


class Migration(migrations.Migration):
    """
    Part 2 of a 3 step migration. Since schema changes need to be separated from data
    migrations, step 1 modifies the BespokeSentSMS class to add the necessary attributes
    for consolidating other sent sms types into its table. Step 2 migrates the data from
    other tables/classes into this one. Step 3 finalizes the migration by removing the
    other tables/classes and renames BespokeSentSMS to SentSMS.
    """
    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('sms', '0043_outgoingsms_from_bespokesentsms_data'),
    ]

    operations = [
        migrations.RunPython(consolidate_sms_messages, reverse_code=reverse_sms_consolidation),
    ]

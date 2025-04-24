
import csv
import os
from datetime import datetime, timedelta
from typing import Iterable

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

import sentry_sdk
import xlsxwriter
from celery.utils.log import get_task_logger
from django_tenants.utils import schema_context

from core.tasks import BaseTask
from core.utils.clients import get_all_clients
from customers.models import Customer
from ishamba.celery import app
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS
from sms.tasks import send_message
from subscriptions.models import Subscription


@app.task(base=BaseTask)
def end_subscriptions():
    for client in get_all_clients():
        with schema_context(client.schema_name):
            active_customers = Customer.objects.premium().values_list('pk', flat=True)
            ended = (Subscription.objects
                                 .exclude(customer__in=active_customers)
                                 .not_permanent()
                                 .not_ended()
                                 .has_end_message()
                                 .expired())
            for values in ended.values_list('id', 'customer_id', 'type__end_message'):
                id, customer_pk, msg = values
                sms = OutgoingSMS.objects.create(text=msg,
                                                 message_type=OUTGOING_SMS_TYPE.SUBSCRIPTION_NOTIFICATION.value,
                                                 extra={'subscription_id': id})

                if settings.ENFORCE_BLACKOUT_HOURS:
                    this_hour_local = timezone.localtime(timezone.now()).hour
                    if settings.BLACKOUT_END_HOUR <= this_hour_local <= settings.BLACKOUT_BEGIN_HOUR:
                        # If we're within the allowed sending hours, send immediately
                        send_message.delay(sms_id=sms.pk, recipient_ids=[customer_pk], sender=settings.SMS_SENDER_SUBSCRIPTION)
                    else:
                        # delay the sending until the next acceptable hour
                        if this_hour_local < settings.BLACKOUT_END_HOUR:
                            eta = datetime.now() + timedelta(hours=settings.BLACKOUT_END_HOUR - this_hour_local)
                        else:
                            eta = datetime.now() + timedelta(hours=(
                                24 - this_hour_local + settings.BLACKOUT_END_HOUR))

                        sentry_sdk.capture_message(f"BLACKOUT: end_subscriptions message {msg} scheduled "
                                                   f"{timezone.localtime(timezone.now())}, delaying until {eta}")

                        send_message.apply_async((sms.id, [customer_pk]),
                                                 kwargs={'sender': settings.SMS_SENDER_SUBSCRIPTION,},
                                                 eta=eta)
                else:
                    send_message.delay(sms_id=sms.id, recipient_ids=[customer_pk], sender=settings.SMS_SENDER_SUBSCRIPTION)

            ended.update(ended=True)


logger = get_task_logger(__name__)


def _remove_archived_lru_files():
    filenames = os.listdir(settings.EMAIL_ATTACHMENT_ARCHIVE_ROOT)
    filenames.remove('README.txt')  # exclude the README file
    archived_files = [os.path.join(settings.EMAIL_ATTACHMENT_ARCHIVE_ROOT, x) for x in filenames]
    while len(archived_files) >= settings.EMAIL_ATTACHMENT_ARCHIVE_MAX_FILES:
        oldest_file = min(archived_files, key=os.path.getctime)
        os.remove(oldest_file)
        archived_files.remove(oldest_file)
        logger.info(f'Removed archived email attachment file: {oldest_file}')


def _generate_csv_attachment(filename: str, headers: list, customer_ids: Iterable[int], fields: Iterable[str]):
    with open(filename, 'w') as attachment:
        csv_writer = csv.writer(attachment, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(headers)
        # For each customer, generate a row in the csv file
        for c_id in customer_ids:
            row = []
            try:
                c = Customer.objects.get(id=c_id)
            except Customer.DoesNotExist:
                csv_writer.writerow([c_id, 'Customer not found!'])
                continue

            # Generate a single spreadsheet row from the fields of this Customer
            for f in fields:
                if f == 'categories':
                    if c.categories.count() > 0:
                        row.append('/ '.join(c.categories.values_list('name', flat=True)))
                    else:
                        row.append('')
                else:
                    row.append(getattr(c, f))
            csv_writer.writerow(row)


def _generate_xlsx_attachment(filename: str, headers: list, customer_ids: Iterable[int], fields: Iterable[str]):
    # Create an new Excel file and add a worksheet.
    workbook = xlsxwriter.Workbook(filename, {
        'remove_timezone': True,
        'default_date_format': 'yyyy-mm-dd HH:mm:ss',
    })
    worksheet = workbook.add_worksheet('Exported Customers')
    # Add formats to use in cells.
    bold_format = workbook.add_format({'bold': True})
    row = 0
    for col, header in enumerate(headers):
        worksheet.write(row, col, header, bold_format)

    # For each customer, generate a row in the xlsx file
    for c_id in customer_ids:
        row += 1
        col = 0
        try:
            c = Customer.objects.get(id=c_id)
        except Customer.DoesNotExist:
            worksheet.write(row, 1, 'Customer not found!', bold_format)
            continue

        # Generate a single spreadsheet row from the fields of this Customer
        for f in fields:
            if f == 'categories':
                if c.categories.count() > 0:
                    worksheet.write(row, col, ', '.join(c.categories.values_list('name', flat=True)))
            else:
                worksheet.write(row, col, getattr(c, f))
            col += 1
    workbook.close()


@app.task(base=BaseTask, bind=True, ignore_result=True)
def send_customers_email_via_celery(self, recipient: str, customer_ids: Iterable[int], fields: Iterable[str], export_format: str = 'csv'):
    """
    Export the selected customers to a sheet (csv or xlsx) and email the report to the recipient
    """
    if not customer_ids or not fields:
        raise ValueError(f"send_customers_email_via_celery: customer_ids {customer_ids} and fields {fields} must not be None")

    base_name = f'Exported Customers {timezone.now().strftime("%Y-%m-%dT%H:%M")}'
    from_email = settings.DEFAULT_FROM_EMAIL
    reply_to = [settings.ADMINS[0][1]]
    subject = f'{settings.EMAIL_SUBJECT_PREFIX} {base_name}'
    cc_recipients = []
    bcc_recipients = []
    message = (f'Attached is the spreadsheet you requested that contains '
               f'the exported customers from iShamba.\n\n-iShamba Admin\n')
    attachment_name = f'{base_name}.{export_format}'
    filename = os.path.join(settings.EMAIL_ATTACHMENT_ARCHIVE_ROOT, attachment_name)

    headers = fields

    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=from_email,
        to=[recipient],
        cc=cc_recipients,
        bcc=bcc_recipients,
        reply_to=reply_to,
    )

    if export_format == 'xlsx':
        _generate_xlsx_attachment(filename, headers, customer_ids, fields)
    else:
        _generate_csv_attachment(filename, headers, customer_ids, fields)

    email.attach_file(filename)
    email.send(fail_silently=False)
    logger.info(f'User {recipient} exported customers to file: {filename}')
    _remove_archived_lru_files()

    notification_email = EmailMessage(
        subject=f'{settings.EMAIL_SUBJECT_PREFIX} {base_name}',
        body=f'User {recipient} exported {len(customer_ids)} customers via email. Exported task filename: {filename}',
        from_email=from_email,
        to=['ishamba@mediae.org'],
        bcc=['lilian@ishamba.org', 'elias@ishamba.org'],
        reply_to=reply_to,
    )
    notification_email.send(fail_silently=True)

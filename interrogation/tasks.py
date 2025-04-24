import csv
import logging
import os
import xlsxwriter
from datetime import datetime, date
from typing import Optional, List

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from celery.utils.log import get_task_logger
from phonenumber_field.phonenumber import PhoneNumber

from core.tasks import BaseTask
from customers.models import Customer, CustomerSurvey
from interrogation.models import InterrogationSession
from ishamba.celery import app


logger: logging.Logger = get_task_logger(__name__)


@app.task(base=BaseTask)
@transaction.atomic
def maybe_register_customer(
    customer_id: int,
    phone_number: PhoneNumber,
    timestamp: Optional[datetime]
):
    """Register customer and send welcome SMS message. When timestamp is provided,
    this task will be ignored unless timestamp is newer than the latest InterrogationSession update time.
    """
    if timestamp:
        session: InterrogationSession = InterrogationSession.objects.filter(
            phone=phone_number).order_by('-created').first()
        if not session or session.last_updated > timestamp:
            # further updates have occurred, this task is no longer relevant
            return
    customer: Customer = Customer.objects.get(pk=customer_id)
    assert customer.main_phone == phone_number
    if customer.is_registered:
        logger.warning(f'Customer {customer.id} is already registered, skipping welcome SMS')
        return
    customer.is_registered = True
    customer.save()
    customer.send_welcome_sms()


def _remove_archived_lru_files():
    filenames = os.listdir(settings.EMAIL_ATTACHMENT_ARCHIVE_ROOT)
    filenames.remove('README.txt')  # exclude the README file
    archived_files = [os.path.join(settings.EMAIL_ATTACHMENT_ARCHIVE_ROOT, x) for x in filenames]
    while len(archived_files) >= settings.EMAIL_ATTACHMENT_ARCHIVE_MAX_FILES:
        oldest_file = min(archived_files, key=os.path.getctime)
        os.remove(oldest_file)
        archived_files.remove(oldest_file)
        logger.info(f'Removed archived email attachment file: {oldest_file}')


def _generate_csv_attachment(filename: str, headers: List[str], survey_title: str, selected_records: Optional[List[int]] = None):
    with open(filename, 'w', newline='') as attachment:
        csv_writer = csv.writer(attachment, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(headers)
        customer_surveys = CustomerSurvey.objects.filter(survey_title=survey_title, finished_at__isnull=False)
        if selected_records:
            customer_surveys = customer_surveys.filter(customer_id__in=selected_records)
        survey_data = [
            [cs.customer.id,cs.customer.formatted_phone, cs.created, cs.finished_at] + [cs.responses.get(header) for header in headers[4:]]
            for cs in customer_surveys
        ]
        # For each customer survey, generate a row in the csv file
        for cs in survey_data:
            csv_writer.writerow(cs)


def _generate_xlsx_attachment(filename: str, headers: List[str], survey_title: str, selected_records: Optional[List[int]] = None):
    # Create a new Excel file and add a worksheet.
    workbook = xlsxwriter.Workbook(filename, {
        'remove_timezone': True,
        'default_date_format': 'yyyy-mm-dd HH:mm:ss',
    })
    worksheet = workbook.add_worksheet('Exported Tasks')
    # Add formats to use in cells.
    bold_format = workbook.add_format({'bold': True})
    date_format = workbook.add_format({'num_format': 'yyyy-mm-dd HH:mm:ss'})
    row = 0

    # Write the headers
    for col, header in enumerate(headers):
        worksheet.write(row, col, header, bold_format)

    # Fetch the survey data
    customer_surveys = CustomerSurvey.objects.filter(survey_title=survey_title, finished_at__isnull=False)
    if selected_records:
        customer_surveys = customer_surveys.filter(customer_id__in=selected_records)
    survey_data = [
        [cs.customer.id,cs.customer.formatted_phone, cs.created, cs.finished_at] + [cs.responses.get(header, '') for header in headers[4:]]
        for cs in customer_surveys
    ]

    # Write data rows
    for data_row in survey_data:
        row += 1
        for col, item in enumerate(data_row):
            if isinstance(item, (date, datetime)):
                worksheet.write(row, col, item, date_format)
            else:
                worksheet.write(row, col, item)

    workbook.close()


@app.task(base=BaseTask, bind=True, ignore_result=True)
def send_survey_email_via_celery(self,recipient: str,survey_title: str, headers: List[str], selected_records: Optional[List[int]] = None, export_format: str = 'csv'):
    """
    Export the selected tasks to a sheet (csv or xlsx) and email the report to the recipient.
    """
    base_name = f'Exported Survey {timezone.now().strftime("%Y-%m-%dT%H:%M")}'
    from_email = settings.DEFAULT_FROM_EMAIL
    reply_to = [settings.ADMINS[0][1]]
    subject = f'{settings.EMAIL_SUBJECT_PREFIX} {base_name}'
    cc_recipients = []
    bcc_recipients = []
    message = (f'Attached is the spreadsheet you requested that contains '
               f'the exported survey records from iShamba.\n\n-iShamba Admin\n')
    attachment_name = f'{base_name}.{export_format}'
    filename = os.path.join(settings.EMAIL_ATTACHMENT_ARCHIVE_ROOT, attachment_name)

    if export_format == 'xlsx':
        _generate_xlsx_attachment(filename, headers, survey_title, selected_records)
    else:
        _generate_csv_attachment(filename, headers, survey_title, selected_records)

    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=from_email,
        to=[recipient],
        cc=cc_recipients,
        bcc=bcc_recipients,
        reply_to=reply_to,
    )

    email.attach_file(filename)
    email.send(fail_silently=False)
    logger.info(f'User {recipient} exported survey records to file: {filename}')
    _remove_archived_lru_files()

    notification_email = EmailMessage(
        subject=f'{settings.EMAIL_SUBJECT_PREFIX} {base_name}',
        body=f'User {recipient} exported {survey_title} data via email. Exported survey records filename: {filename}',
        from_email=from_email,
        to=['ishamba@mediae.org'],
        bcc=['lilian@ishamba.org', 'elias@ishamba.org'],
        reply_to=reply_to,
    )
    notification_email.send(fail_silently=True)

import csv
import io
import os
from typing import Iterable

import xlsxwriter

from celery.utils.log import get_task_logger

from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.utils import timezone

from ishamba.celery import app
from core.tasks import BaseTask
from .models import Task

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


def _generate_csv_attachment(filename: str, headers: list, task_ids: Iterable[int], fields: Iterable[str]):
    with open(filename, 'w') as attachment:
        csv_writer = csv.writer(attachment, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(headers)
        # For each task, generate a row in the csv file
        for t_id in task_ids:
            row = [t_id]  # Start with the task_id
            try:
                t = Task.objects.get(id=t_id)
            except Task.objects.DoesNotExist:
                csv_writer.writerow([t_id, 'Task not found!'])
                continue

            # Generate a single spreadsheet row from the fields of this Task
            for f in fields:
                if f == 'responses':
                    if t.outgoing_messages.count() > 0:
                        row.append(', '.join(t.outgoing_messages.values_list('text', flat=True)))
                    else:
                        row.append('')
                elif f == 'tags':
                    if t.tags.count() > 0:
                        row.append(', '.join(t.tags.values_list('name', flat=True)))
                    else:
                        row.append('')
                elif f == 'assignees':
                    if t.assignees.count() > 0:
                        row.append(', '.join(t.assignees.values_list('username', flat=True)))
                    else:
                        row.append('')
                elif f == 'customer_border0':
                    border0 = t.customer.border0
                    if border0:
                        row.append(border0.name)
                    else:
                        row.append('')
                elif f == 'customer_border1':
                    border1 = t.customer.border1
                    if border1:
                        row.append(border1.name)
                    else:
                        row.append('')
                elif f == 'customer_has_gps':
                    if t.customer.location:
                        row.append(f"{t.customer.location.y}, {t.customer.location.x}")
                    else:
                        row.append('')

                elif f in ('status', 'priority'):
                    txt = getattr(t, f) if getattr(t, f) else ''
                    row.append(txt.title())
                else:
                    row.append(getattr(t, f))
            csv_writer.writerow(row)


def _generate_xlsx_attachment(filename: str, headers: list, task_ids: Iterable[int], fields: Iterable[str]):
    # Create an new Excel file and add a worksheet.
    workbook = xlsxwriter.Workbook(filename, {
        'remove_timezone': True,
        'default_date_format': 'yyyy-mm-dd HH:mm:ss',
    })
    worksheet = workbook.add_worksheet('Exported Tasks')
    # Add formats to use in cells.
    bold_format = workbook.add_format({'bold': True})
    date_format = workbook.add_format({'num_format': 'yyyy-mm-dd HH:mm:ss'})
    row = 0
    for col, header in enumerate(headers):
        worksheet.write(row, col, header, bold_format)

    # For each task, generate a row in the xlsx file
    for t_id in task_ids:
        row += 1
        col = 0
        worksheet.write_number(row, col, int(t_id))

        try:
            t = Task.objects.get(id=t_id)
        except Task.DoesNotExist:
            worksheet.write_number(row, 0, t_id)
            worksheet.write(row, 1, 'Task not found!', bold_format)
            continue

        # Generate a single spreadsheet row from the fields of this Task
        for f in fields:
            col += 1
            if f == 'responses':
                if t.outgoing_messages.count() > 0:
                    worksheet.write(row, col, ', '.join(t.outgoing_messages.values_list('text', flat=True)))
                else:
                    worksheet.write(row, col, '')
            elif f == 'tags':
                if t.tags.count() > 0:
                    worksheet.write(row, col, ', '.join(t.tags.values_list('name', flat=True)))
                else:
                    worksheet.write(row, col, '')
            elif f == 'assignees':
                if t.assignees.count() > 0:
                    worksheet.write(row, col, ', '.join(t.assignees.values_list('username', flat=True)))
                else:
                    worksheet.write(row, col, '')
            elif f == 'customer_border0':
                border0 = t.customer.border0
                if border0:
                    worksheet.write(row, col, border0.name)
                else:
                    worksheet.write(row, col, '')
            elif f == 'customer_border1':
                border1 = t.customer.border1
                if border1:
                    worksheet.write(row, col, border1.name)
                else:
                    worksheet.write(row, col, '')
            elif f == 'customer_has_gps':
                if t.customer.location:
                    worksheet.write(row, col, f"{t.customer.location.y}, {t.customer.location.x}")
                else:
                    worksheet.write(row, col, '')
            elif f in ('created', 'last_updated'):
                worksheet.write_datetime(row, col, getattr(t, f), date_format)
            elif f in ('status', 'priority'):
                txt = getattr(t, f) if getattr(t, f) else ''
                worksheet.write(row, col, txt.title())
            else:
                worksheet.write(row, col, getattr(t, f))
    workbook.close()



@app.task(base=BaseTask, bind=True, ignore_result=True)
def send_tasks_email_via_celery(self, recipient: str, task_ids: Iterable[int], fields: Iterable[str], export_format: str = 'csv'):
    """
    Export the selected tasks to a sheet (csv or xlsx) and email the report to the recipient
    """
    if not task_ids or not fields:
        raise ValueError(f"send_tasks_email_via_celery: task_ids {task_ids} and fields {fields} must not be None")

    base_name = f'Exported Tasks {timezone.now().strftime("%Y-%m-%dT%H:%M")}'
    from_email = settings.DEFAULT_FROM_EMAIL
    reply_to = [settings.ADMINS[0][1]]
    subject = f'{settings.EMAIL_SUBJECT_PREFIX} {base_name}'
    cc_recipients = []
    bcc_recipients = []
    message = (f'Attached is the spreadsheet you requested that contains '
               f'the exported tasks from iShamba.\n\n-iShamba Admin\n')
    attachment_name = f'{base_name}.{export_format}'
    filename = os.path.join(settings.EMAIL_ATTACHMENT_ARCHIVE_ROOT, attachment_name)

    headers = ['task_id']  # task_id is not a choice given in the export form. Always include it.

    for f in fields:
        if f == 'customer_border0':
            headers.append('country')
        elif f == 'customer_border1':
            headers.append('county/region')
        else:
            headers.append(f)

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
        _generate_xlsx_attachment(filename, headers, task_ids, fields)
    else:
        _generate_csv_attachment(filename, headers, task_ids, fields)

    email.attach_file(filename)
    email.send(fail_silently=False)
    logger.info(f'User {recipient} exported tasks to file: {filename}')
    _remove_archived_lru_files()

    notification_email = EmailMessage(
        subject=f'{settings.EMAIL_SUBJECT_PREFIX} {base_name}',
        body=f'User {recipient} exported {len(task_ids)} tasks via email. Exported task filename: {filename}',
        from_email=from_email,
        to=['ishamba@mediae.org'],
        bcc=['lilian@ishamba.org', 'elias@ishamba.org'],
        reply_to=reply_to,
    )
    notification_email.send(fail_silently=True)

import argparse
from datetime import datetime, timedelta
import time

from django.core.management.base import BaseCommand
from django.db import connection
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from django_tenants.management.commands import InteractiveTenantOption

from customers.models import Customer
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS
from sms.tasks import send_message
from world.models import Border


class Command(BaseCommand, InteractiveTenantOption):
    help = 'Export interesting customers records to csv'

    # Usage: ./manage.py send-location-query -t -v1 -n 1000 -d 10 -s ishamba

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("-d", "--delay", dest="delay_hours",
                            type=int, default=0, help="hours to delay before sending")
        parser.add_argument('-n', '--number', required=True, type=int, dest='number', action='store',
                            default=100, help='number of customers to send query to')
        parser.add_argument("-s", "--schema", dest="schema_name", help="tenant schema", default="ishamba")
        parser.add_argument("-t", "--test", dest="test_run", action='store_true',
                            help="test run: no sms messages are sent")

    def handle(self, *args, **options):
        # Track performance for summary report
        tic = time.perf_counter()

        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)

        delay_hours = options['delay_hours']
        number = options['number']
        verbosity = options['verbosity']
        test_run = options['test_run']

        # When the call centre is closed
        msg = "Thanks for being a member of iShamba, the Shamba Shape Up farmer support service. Each week " \
              "we send free weather forecasts and advice on how to adapt to climate change. If you would like to " \
              "receive these, please send us the WARD that your shamba is in or ask your farm questions to 21606."

        # When the call centre is open

        # msg = "Thanks for being a member of iShamba, the Shamba Shape Up farmer support service. Each week " \
        #       "we send weather forecasts and advice on how to adapt to climate change. If you would like to " \
        #       "receive these, please reply with the WARD of your shamba or call 0711082606."

        # Find the stopped candidates in the DB
        # candidate_ids = list(Customer.objects.filter(
        #     has_requested_stop=True,
        #     stop_method='?',
        #     stop_date__isnull=True,
        #     location__isnull=True,
        #     border3__isnull=True
        # ).filter(
        #     phones__number__startswith='+254'
        # ).order_by('?').values_list('id', flat=True)[:number])

        msg = "iShamba sends free weekly weather and drought forecasts. If you would like to receive these, " \
              "please reply with the name of your Ward or call 0711082606."

        # How recent we consider the most recent query response to still be active
        earliest_date = timezone.localtime(timezone.now()) - timedelta(days=180)
        response_window = timezone.localtime(timezone.now()) - timedelta(days=5)

        kenya = Border.objects.get(country='Kenya', level=0)

        # Find customers without border3 who have not been asked their location recently
        candidate_ids = set(Customer.objects.filter(
            has_requested_stop=False,
            location__isnull=True,
            border3__isnull=True,
            border0=kenya,
            preferred_language='eng',
            id__gt=100,  # Don't include initial staff or customer set
            # phones__number__startswith='+254',
        ).order_by('?').values_list('id', flat=True))
        data_request_ids = set(
            OutgoingSMS.objects.filter(
                message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
                time_sent__gte=earliest_date).values_list('recipients__recipient__id', flat=True)
        )
        nps_ids = set(
            OutgoingSMS.objects.filter(
                message_type=OUTGOING_SMS_TYPE.NPS_REQUEST,
                time_sent__gte=response_window).values_list('recipients__recipient__id', flat=True)
        )

        candidate_ids = list(candidate_ids - data_request_ids - nps_ids)[:number]

        if verbosity:
            print(f"Chosen customers: {candidate_ids}")

        kwargs = {}
        if delay_hours:
            eta = timezone.now() + timedelta(hours=delay_hours)  # Delay message delivery by N hours
            task_kwargs = {'eta': eta}
            kwargs = {'task_kwargs': task_kwargs}

        if len(candidate_ids) > 0:
            try:
                if not test_run:
                    # Disable their has_requested_stop flag so that we can send them this message.
                    # candidates.update(has_requested_stop=False)
                    sms = OutgoingSMS.objects.create(text=msg,
                                                     message_type=OUTGOING_SMS_TYPE.DATA_REQUEST )
                    send_message.delay(sms.id, candidate_ids, sender='21606', exclude_stopped_customers=False, **kwargs)

                if verbosity:
                    print(f"Sent to customers: {candidate_ids}")
            except ValidationError:  # e.g. invalid phone numbers
                print("ValidationError: ", candidate_ids)
                # For now, skip the batch and continue. TODO: Implement partial retry.
                pass

            toc = time.perf_counter()
            print(msg)
            print(f"Message sent to {len(candidate_ids)} customers in {toc - tic:0.1f} secs, "
                  f"{len(candidate_ids) / (toc - tic):0.1f}/s")
        else:
            print("WARNING: No customers found for message")

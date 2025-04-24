import argparse
import time as perftime
from decimal import Decimal
from datetime import datetime, date, timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import F, Sum

from django_tenants.management.commands import InteractiveTenantOption

from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS, SMSRecipient, DailyOutgoingSMSSummary
from world.models import Border


def daterange(start_date, end_date):
    """ Produce a sequence of dates (forward or backwards), inclusive of both ends """
    backwards = start_date > end_date
    delta = abs((start_date - end_date).days) + 1  # To make the dates range inclusive
    if backwards:
        seq_range = range(0, -delta, -1)
    else:
        seq_range = range(0, delta, 1)  # dates, inclusive
    for n in seq_range:
        yield start_date + timedelta(n)


class Command(BaseCommand, InteractiveTenantOption):
    help = 'Calculate the sms costs for a batch days'

    # Usage: ./manage.py migrate-sentsms-batch -t -v 1 -n <<batch_size>> -d '2021-10-05' -s ishamba

    def add_arguments(self, parser: argparse.ArgumentParser):

        parser.add_argument("-n", "--num_days", dest="num_days", required=True,
                            type=int, help="number of days BEFORE THE START DAY to start converting")
        parser.add_argument("-d", "--date", dest="first_day", required=True,
                            default=date.today() - timedelta(days=1),
                            type=lambda d: datetime.strptime(d, '%Y-%m-%d').date(),
                            help="the first day to calculate costs for with format yyyy-mm-dd")
        parser.add_argument("-f", "--force", dest="force", required=False, action='store_true',
                            help="force a recalculation on the specified days")
        parser.add_argument("-s", "--schema", default="ishamba", dest="schema_name", help="tenant schema")
        parser.add_argument("-t", "--test", dest="test_run", action='store_true',
                            help="test run: no sms messages are sent")
        # parser.add_argument("-v", "--verbose", action="count", default=0,
        #                     help="increase output verbosity")

    def handle(self, *args, **options):

        # Track performance for summary report
        tic = perftime.perf_counter()

        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)

        first_day = options['first_day']
        num_days = options['num_days'] - 1  # Otherwise we calculate one too many days
        last_day = first_day - timedelta(days=num_days)
        force = options['force']
        schema_name = options['schema_name']

        verbosity = options['verbosity']
        test_run = options['test_run']

        # Now update all DailyOutgoingSMSSummary objects with new stats
        kenya_id = Border.objects.get(level=0, name="Kenya").id

        created_count = 0
        updated_count = 0

        # We create distinct objects for each country/day/gateway_name/message_type combination
        for day in daterange(first_day, last_day):  # backwards, inclusive of both ends
            prev_summary = DailyOutgoingSMSSummary.objects.filter(date=day, country_id=kenya_id).first()
            if not force and prev_summary and prev_summary.last_updated.date() > date(2022, 2, 21):
                print(f"Skipping {schema_name} {day}: Already summarized")
                continue
            print(f"--------------------------------------")
            print(f"*** Summarizing {schema_name} {day}  at {datetime.now()} ***")
            print(f"--------------------------------------")

            for type_obj in OUTGOING_SMS_TYPE:
                msg_type = type_obj.value
                if msg_type == '?':
                    continue
                t1 = perftime.perf_counter()
                message_ids = list(OutgoingSMS.objects.filter(created__date=day,
                                                              message_type=msg_type) \
                                   .values_list('id', flat=True))
                t2 = perftime.perf_counter()
                if not message_ids:
                    print(f"Skipping {msg_type}: no records.  t2-t1={t2-t1:0.1f}")
                    continue
                message_ids.sort()
                costs = SMSRecipient.objects.filter(message_id__in=message_ids,
                                                    gateway_name='AfricasTalking').values_list('cost', flat=True)
                count = costs.count()
                t3 = perftime.perf_counter()
                # Hard code to be kenya shillings, since all messages were sent via AT in Kenya so far
                cost_units = 'kes'
                total_cost = sum(map(Decimal, costs))
                t4 = perftime.perf_counter()
                if not test_run:
                    obj, created = DailyOutgoingSMSSummary.objects.update_or_create(
                        date=day,
                        country_id=kenya_id,
                        message_type=msg_type,
                        defaults={
                            'gateway_name': 'AfricasTalking',
                            'count': count,
                            'cost': total_cost,
                            'cost_units': cost_units,
                            'extra': {'message_ids': message_ids}
                        }
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                t5 = perftime.perf_counter()
                if verbosity:
                    print(f"{msg_type}: t2-t1={t2-t1:0.1f}, t3-t2={t3-t2:0.1f}, t4-t3={t4-t3:0.1f}, t5-t4={t5-t4:0.1f}")

        if verbosity:
            toc = perftime.perf_counter()
            print(f"Created {created_count} and updated {updated_count} DailyOutgoingSMSSummary "
                  f"objects in {toc - tic:0.1f}s")

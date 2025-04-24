import argparse
import csv
from collections import defaultdict
from datetime import datetime, timedelta
import time

from django.core.management.base import BaseCommand
from django.db import connection
from django.core.exceptions import ValidationError
from django.db.models import Q

from world.models import Border

from django_tenants.management.commands import InteractiveTenantOption

from customers.models import Customer


class Command(BaseCommand, InteractiveTenantOption):
    help = 'Export interesting customers records to csv'

    # Usage: ./manage.py export-customers -t -v1 -f output.csv -s ishamba

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument('-o', '--output_file', required=True,
                            type=argparse.FileType('w'), help='csv output file')
        parser.add_argument("-l", "--require-location", dest="location",
                            action='store_true', help="only include customers with locations")
        parser.add_argument("-s", "--schema", dest="schema_name", help="tenant schema", default="ishamba")
        parser.add_argument("-t", "--test", dest="test_run", action='store_true',
                            help="test run: no sms messages are sent")
        # parser.add_argument("-f", "--filter", dest="filter_expression", action='store_true',
        #                     help="an extra expression to add to filters")
        # parser.add_argument("-v", "--verbose", action="count", default=0,
        #                     help="increase output verbosity")

    def handle(self, *args, **options):
        # Track performance for summary report
        tic = time.perf_counter()

        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)

        verbosity = options['verbosity']
        test_run = options['test_run']
        output_file = options['output_file']
        require_location = options['location']

        # A list of Customer fields to exclude from the generated report
        excludes = [
            'action_object_actions', 'actor_actions', 'can_access_call_centre', 'heard_about_us',
            'last_editor', 'last_editor_id', 'last_updated', 'misc_data', 'border1',
            'border2', 'border3', 'bank', 'cooperative', 'date_registered',
            'postal_address', 'postal_code', 'savings_coop', 'savings_coop_id',
            'phones', 'digifarm_farmer_id', 'weather_area_id', 'weather_area',
            'creator', 'creator_id', 'context', 'formatted_phone', 'id_number', 'tasks',
            'incomingsms_set', 'is_lapsed', 'is_registered', 'never_subscribed', 'notes',
            'objects', 'pk', 'main_phone', 'should_receive_messages',
            'smsrecipient_set', 'bank_id', 'cooperative_id', 'target_actions',
            'tip_subscriptions', 'used_vouchers', 'region_id',
            # The following are excluded from automated extraction, and handled separately
            'answers', 'call_set', 'categories', 'commodities',
            'market_subscriptions', 'markets', 'subscriptions',
            'crophistory_set', 'currently_subscribed', 'sent_sms',
        ]

        # Get a list of all Customer fields
        fields = [attr for attr in dir(Customer) if not callable(getattr(Customer, attr))
                  and not attr.startswith("_") and not attr.isupper()]

        fields = [field for field in fields if field not in excludes]
        headers = fields + ['call_count', 'sms_received_count', 'categories', 'commodities']

        csv_writer = csv.writer(output_file, delimiter=',',
                                quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(headers)

        if (require_location):
            customers = Customer.objects.filter(location__isnull=False)
        else:
            customers = Customer.objects.all()

        customers = customers.exclude(has_requested_stop=True)
        border1_id = Border.objects.filter(country="Kenya", level=1, name="Meru").first().id
        customers = customers.filter(border1_id=border1_id)

        customer_count = 0
        for customer in customers:
            values = []
            for field in fields:
                values.append(getattr(customer, field))

            call_count = customer.call_set.count()
            values.append(call_count)

            sms_count = customer.incomingsms_set.count()
            values.append(sms_count)

            categories = customer.categories.all()
            category_names = ','.join([c.name for c in categories])
            values.append(category_names)

            commodities = customer.commodities.all()
            commodity_names = ','.join([c.name for c in commodities])
            values.append(commodity_names)

            csv_writer.writerow(values)

            customer_count += 1
            toc = time.perf_counter()
            if customer_count % 5000 == 0:
                print(f"Exported {customer_count} customers in {toc - tic:0.1f} secs, {customer_count/(toc - tic):0.1f}/s")

        toc = time.perf_counter()

        print(f"{customer_count} customers exported in {toc - tic:0.1f} seconds")

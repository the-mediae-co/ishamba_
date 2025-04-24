import argparse
import csv
import time

from django.core.management.base import BaseCommand
from django.db import connection

from django_tenants.management.commands import InteractiveTenantOption

from customers.models import Customer


class Command(BaseCommand, InteractiveTenantOption):
    help = 'Export interesting customers records to csv'

    # Usage: ./manage.py export-customers -t -v1 -f output.csv -s ishamba

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument('-o', '--output_file', required=True,
                            type=argparse.FileType('w'), help='csv output file')
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

        headers = ['customer_id', 'location']

        csv_writer = csv.writer(output_file, delimiter=',',
                                quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(headers)

        customers = Customer.objects.filter(location__isnull=False)
        customers = customers.exclude(has_requested_stop=True)

        customer_count = 0
        for customer in customers:
            csv_writer.writerow([customer.pk, customer.location])

            customer_count += 1
            toc = time.perf_counter()
            if customer_count % 10000 == 0:
                print(f"Exported {customer_count} customers in {toc - tic:0.1f} secs, {customer_count/(toc - tic):0.1f}/s")

        toc = time.perf_counter()

        print(f"{customers.count()} customers exported in {toc - tic:0.1f} seconds")

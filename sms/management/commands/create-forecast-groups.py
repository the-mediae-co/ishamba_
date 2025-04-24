import argparse
import csv
import re
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import connection

from django_tenants.management.commands import InteractiveTenantOption


class Command(BaseCommand, InteractiveTenantOption):
    help = 'Group PlantVillage farmers in preparation for sending common weather forecast SMS messages'

    # Usage: ./manage.py send-forecasts -t -v1 -f ishamba_messages.csv

    # csv file column headers
    CUSTOMER_ID_COLUMN_TITLE = "customer_id"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument('-f', '--file', required=True,
                            type=argparse.FileType('r'), help='membership file')
        parser.add_argument("-s", "--schema", dest="schema_name",
                            help="tenant schema", default="ishamba")
        # parser.add_argument("-t", "--test", dest="test_run", action='store_true',
        #                     help="test run: no sms messages are sent")
        # parser.add_argument("-v", "--verbose", action="count", default=0,
        #                     help="increase output verbosity")

    def handle(self, *args, **options):
        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)

        verbosity = options['verbosity']
        # test_run = options['test_run']
        input_file = options['file']

        csv_reader = csv.reader(input_file, delimiter=',', quotechar='"')
        column_headers = next(csv_reader)

        customer_column = column_headers.index(self.CUSTOMER_ID_COLUMN_TITLE)

        nearterm_column = None
        spei_column = None

        nearterm_pattern = re.compile('^202\d\d\d\d\d_')
        spei_pattern = re.compile('^SPEI_')
        col_index = -1
        nearterm_found = False
        spei_found = False
        for col in column_headers:
            col_index += 1
            if nearterm_pattern.match(col):
                nearterm_column = col_index
                nearterm_found = True
            elif spei_pattern.match(col):
                spei_column = col_index
                spei_found = True

        if not nearterm_found:
            raise ValidationError("Forecast column not found")
        if not spei_found:
            raise ValidationError("SPEI column not found")

        group_members = defaultdict(list)

        with open('membership.csv', 'w', newline='') as member_file:
            member_writer = csv.writer(member_file, delimiter=',',
                                       quotechar='"', quoting=csv.QUOTE_MINIMAL)
            member_writer.writerow(['customer_id', 'group_id'])
            for row in csv_reader:
                customer_id = int(row[customer_column])
                # total_rain_forecast = str(round(float(row[total_column])))
                # start_date_str = str(row[start_date_column])
                nearterm_rain = round(float(row[nearterm_column]))
                if nearterm_rain < 0:
                    nearterm_rain = 0
                nearterm_rain = str(nearterm_rain)

                spei_risk = round(float(row[spei_column])*-100)
                # if spei_risk > 100:
                #     spei_risk = 100
                # elif spei_risk < 0:
                #     spei_risk = 0

                high_spei_risk = 69
                medium_spei_risk = 39

                spei_risk_str = "low"
                if spei_risk > high_spei_risk:
                    spei_risk_str = "high"
                elif spei_risk > medium_spei_risk:
                    spei_risk_str = "medium"

                # start_date = datetime.strptime(start_date_str, '%Y-%m-%d')

                # group_key = '~'.join([start_date_str, total_rain_forecast, nearterm_rain])
                group_key = '~'.join([spei_risk_str, nearterm_rain])
                group_members[group_key].append(customer_id)

                member_writer.writerow([customer_id, group_key])

        # for group in group_members.keys():
        #     print(group, len(group_members[group]))

        print(f"{len(group_members)} groups identified")

        with open('forecasts.csv', 'w', newline='') as forecast_file:
            forecast_writer = csv.writer(forecast_file, delimiter=',',
                                         quotechar='"', quoting=csv.QUOTE_MINIMAL)
            # forecast_writer.writerow(['group_id', 'forecasted_start_date', 'total_forecasted',
            #                           'nearterm_forecast', 'total_measured', 'num_members'])
            forecast_writer.writerow(['group_id', 'spei_risk',
                                      'nearterm_forecast', 'num_members'])
            for group in group_members.keys():
                spei_risk, nearterm_rain = group.split('~')
                # nearterm_rain = group
                forecast_writer.writerow([group, spei_risk,
                                          nearterm_rain, len(group_members[group])])

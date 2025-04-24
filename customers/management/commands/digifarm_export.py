from __future__ import absolute_import, unicode_literals
import argparse
import csv
import datetime

from django.core.management.base import BaseCommand
from django.utils import formats, translation

from customers.models import Customer


def valid_date(s):
    try:
        format_strings = formats.get_format("DATE_INPUT_FORMATS", lang=translation.get_language())
        return datetime.datetime.strptime(s, format_strings)
    except ValueError:
        raise argparse.ArgumentType("Not a valid date")


class Command(BaseCommand):
    help = 'Export customers added since a given date that are not on digifarm'

    def add_arguments(self, parser):
        parser.add_argument('after_date', type=valid_date)
        parser.add_argument('out_file', type=argparse.FileType('w'))

    def handle(self, after_date, out_file=None, *args, **options):
        pks = Customer.objects.premium().values_list('pk', flat=True)

        customers = (Customer.objects.filter(date_registered__gte=after_date)
                                     .exclude(pk__in=pks)
                                     .should_receive_messages()
                                     .africas_talking_only())

        self.stdout.write("Found {} customers to export".format(customers.count()))

        customer_dicts = [{
            'firstName': c.name.partition(' ')[0].encode('utf8'),
            'lastName': c.name.partition(' ')[2].encode('utf8'),
            'mobileNumber': c.phone,
            'farmLatitude': c.location.y,
            'farmLongitude': c.location.x,
        } for c in customers]

        headers = ['location', 'firstName', 'middleName', 'lastName', 'mobileNumber',
                   'nationalId', 'dateOfBirth', 'gender', 'postalAddress',
                   'physicalAddress', 'farmDescription', 'farmLatitude',
                   'farmLongitude', 'cropTypeName', 'cropSize',
                   'valueChainStartDate', 'valueChainEndDate', 'registeredOnFarm']

        with out_file:
            out_file.write(u'\ufeff'.encode('utf8'))
            writer = csv.DictWriter(out_file, fieldnames=headers)
            writer.writeheader()
            for customer in customer_dicts:
                writer.writerow(customer)

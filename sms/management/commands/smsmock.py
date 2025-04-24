import argparse

from django.core.management.base import BaseCommand
import requests

from sms.tests.utils import get_sms_data


class Command(BaseCommand):
    help = 'Mocks receiving SMSs'

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument('--text', '-t', help='SMS TEXT')
        parser.add_argument('--from', '-f', metavar='FROM', help='SMS FROM number')
        parser.add_argument('--number-to', metavar='NUMBER TO', help='SMS TO number')

    def handle(self, *args, **options):

        if not options['from']:
            print("Please enter a FROM number using -f")
            return

        if not options['text']:
            print("Please enter the message TEXT number using -t")
            return

        if not options['number_to']:
            number_to = '999'
        else:
            number_to = options['number_to']

        data = get_sms_data(options['text'], options['from'], number_to)

        print("* Here's the POST data *")
        for k, v in data.items():
            print("{0}={1}".format(k, v))

        resp = requests.post('http://localhost:7000/sms/incoming_sms_callback/', data=data)
        resp.raise_for_status()
        print("* Here's the RESPONSE data: *")
        print(resp.content)

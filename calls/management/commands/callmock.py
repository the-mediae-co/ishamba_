import argparse

from urllib import request, parse

from django.core.management.base import BaseCommand
from django.db import connection

from calls.models import PusherSession
from calls.tests.util import (get_dequeue_call_data, get_hang_call_data,
                              get_hang_up_dequeue_call_data,
                              get_make_call_data, get_make_dequeue_call_data)

from django_tenants.management.commands import InteractiveTenantOption


class Command(BaseCommand, InteractiveTenantOption):
    help = 'Mocks calls to the phone callback'

    def add_arguments(self, parser: argparse.ArgumentParser):
        # parser.add_argument("-d", "--delay", dest="delay_hours",
        #                     type=int, default=0, help="hours to delay before sending")
        parser.add_argument('--action', '-a', dest='action', default="call",
                            help='Do ACTION (call, hang, dequeue, dequeue_ok) -- default is call')
        parser.add_argument('--from', '-f', dest='from', default="+254724875817",
                            help='Call FROM number')
        parser.add_argument('--session_id', '-i', dest='session', default="999",
                            help='SESSION ID number')
        parser.add_argument('--dequeue_to', '-d', dest='dequeue_to', help='DEQUEUE TO phone number')
        parser.add_argument('--schema', '-s', dest='schema_name', default="ishamba",
                            help='tenant schema for connection')

    def handle(self, *args, **options):
        if options['action']:
            if options['action'] in ('call', 'hang', 'dequeue', 'dequeue_hang', 'dequeue_ok'):
                action = options['action']
            else:
                print("ACTION should be either call, hang, dequeue or dequeue_ok")
                return

        session = options['session']

        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)

        if action == 'call':
            data = get_make_call_data(session_id=session, caller_number=options['from'])
        elif action == 'dequeue':
            data = get_make_dequeue_call_data(options['from'])
        elif action == 'hang':
            data = get_hang_call_data(session, options['from'])
        elif action == 'dequeue_hang':
            data = get_hang_up_dequeue_call_data(options['from'])
        else:
            if not options['dequeue_to']:
                print("Please enter a DEQUEUE TO number using -d")
                return
            try:
                cco_session = PusherSession.objects.connected().get(call_center_phone__phone_number=options['dequeue_to'])
            except PusherSession.DoesNotExist:
                print("CCO with that number doesn't seem to have an active pusher session")
                return
            data = get_dequeue_call_data(session, options['from'], cco_session.provided_call_id)

        print("* Here's the POST data *")
        for k, v in data.items():
            print("{0}={1}".format(k, v))

        enc_data = parse.urlencode(data).encode()
        req = request.Request('http://localhost:7000/calls/voice_api_callback/', data=enc_data)
        resp = request.urlopen(req)
        print("* Here's the RESPONSE data: *")
        print(resp.read())

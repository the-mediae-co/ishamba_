from tips.tasks import send_scheduled_tips
import argparse
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Send scheduled tips'

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument('--delay_days', '-d', metavar='DELAY DAYS', help='Days ago or in future', type=int, required=False)
        parser.add_argument('--test', '-t', metavar='TEST', help='Report only', type=bool, default=False)

    def handle(self, *args, **options):
        delay_days = options.get('delay_days')
        test = options.get('test')

        tips_for = None
        if delay_days:
            tips_for = timezone.now().date() + timedelta(days=delay_days)

        send_scheduled_tips.delay(tips_for=tips_for, report_only=test)

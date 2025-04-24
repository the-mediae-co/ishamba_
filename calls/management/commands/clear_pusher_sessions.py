import datetime

from django.core.management.base import BaseCommand

from calls.models import PusherSession


class Command(BaseCommand):
    help = 'Clears all pusher session data (to help testing)'

    def handle(self, *args, **options):
        PusherSession.objects.filter(finished_on__isnull=True).update(finished_on=datetime.datetime.now())
        print("OK")

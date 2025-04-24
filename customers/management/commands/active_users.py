

import calendar
from logging import getLogger

from django.core.management.base import BaseCommand
from django.db.models import Count, Func

from calls.models import Call
from sms.models import IncomingSMS

logger = getLogger(__name__)


class Extract(Func):
    """
    Performs extraction of `what_to_extract` from `*expressions`.

    Arguments:
        *expressions (string): Only single value is supported, should be field name to
                               extract from.
        what_to_extract (string): Extraction specificator.

    Returns:
        class: Func() expression class, representing 'EXTRACT(`what_to_extract` FROM `*expressions`)'.
    """

    function = 'EXTRACT'
    template = '%(function)s(%(what_to_extract)s FROM %(expressions)s)'


class Command(BaseCommand):
    help = 'Outputs the monthly active user statistics'

    def handle(self, *args, **options):
        calls = (Call.objects
                 .annotate(
                     year=Extract('created_on', what_to_extract='year'),
                     month=Extract('created_on', what_to_extract='month')
                 )
                 .values('year', 'month')
                 .annotate(count=Count('customer_id', distinct=True))
                 .order_by('year', 'month'))

        print("Calls")
        self._print_statistics(calls)

        sms = (IncomingSMS.objects
               .annotate(
                   year=Extract('created', what_to_extract='year'),
                   month=Extract('created', what_to_extract='month')
               )
               .values('year', 'month')
               .annotate(count=Count('customer_id', distinct=True))
               .order_by('year', 'month'))

        print("\nSMS")
        self._print_statistics(sms)

    def _print_statistics(self, stats):
        last_year = None
        for month in stats:
            if month['year'] != last_year:
                print('\n{}\n'.format(int(month['year'])))
                last_year = month['year']

            print('{}: {}'.format(calendar.month_abbr[int(month['month'])],
                                  month['count']))

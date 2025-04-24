from django.test import override_settings
from django.utils import timezone

from calls.models import Call
from calls.tasks import clear_all_call_states
from customers.tests.factories import CustomerFactory

from core.test.cases import TestCase


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ClearCallStateTestCase(TestCase):
    def test_send_message_single_recipient(self):
        customer = CustomerFactory()
        Call.objects.create(
            created_on=timezone.now(),
            connected_on=timezone.now(),
            hanged_on = None,
            provided_id="AT",
            caller_number=customer.main_phone,
            destination_number="+254720123456",
            customer=customer,
            direction='',
            duration=None,
            duration_in_queue=None,
            cost=None,
            cco=None,
            is_active=True,
            connected=True,
            issue_resolved=False,
            notes=None,
        )
        self.assertEqual(1, Call.objects.filter(is_active=True).count())
        self.assertEqual(1, Call.objects.filter(connected=True).count())
        clear_all_call_states.delay()
        self.assertEqual(0, Call.objects.filter(is_active=True).count())
        self.assertEqual(0, Call.objects.filter(connected=True).count())

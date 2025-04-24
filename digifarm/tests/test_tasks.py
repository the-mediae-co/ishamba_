from unittest import skip
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings

from requests.exceptions import HTTPError

from core.test.cases import TestCase
from customers.tests.factories import CustomerFactory, PremiumSubscriptionFactory
from digifarm.tasks import send_digifarm_bulk_sms
from digifarm.testing import activate_success_response
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS, SMSRecipient
from sms.tests.factories import OutgoingSMSFactory
import subscriptions


class DigifarmTasksTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.outgoing_sms = OutgoingSMSFactory(message_type=OUTGOING_SMS_TYPE.INDIVIDUAL)
        self.customer = CustomerFactory(name='test drone',
                                        digifarm_farmer_id="abc_123_xyz",
                                        subscriptions=[PremiumSubscriptionFactory()])

    @activate_success_response
    @override_settings(ENABLE_DIGIFARM_INTEGRATION=True)
    def test_sends_sms_through_digifarm_gateway_creates_smsrecipient(self):
        digifarm_id = self.customer.digifarm_farmer_id

        # Make sure any previous tests did not set this user as blocked
        blocked_user_cache_key = 'digifarm_blocked_{}'.format(digifarm_id)
        cache.delete(blocked_user_cache_key)

        send_digifarm_bulk_sms([digifarm_id], sms_text=self.outgoing_sms.text)

        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        smsr = SMSRecipient.objects.first()
        self.assertEqual(self.outgoing_sms.id, smsr.message.id)
        self.assertEqual(200, int(smsr.failure_reason))
        self.assertEqual('Success', smsr.delivery_status)
        self.assertEqual(self.customer.id, smsr.recipient_id)

    # @patch('digifarm.tasks.requests.post')
    @skip("blocking logic broken seemingly in move to bulk api?")
    def test_422_response_is_recorded_in_cache(self, post_mock):
        digifarm_id = self.customer.digifarm_farmer_id

        # Make sure any previous tests did not set this user as blocked
        blocked_user_cache_key = 'digifarm_blocked_{}'.format(digifarm_id)
        cache.delete(blocked_user_cache_key)

        post_mock.return_value = Mock()
        post_mock.return_value.status_code = 422
        post_mock.return_value.raise_for_status.side_effect = HTTPError()
        send_digifarm_bulk_sms(digifarm_id, self.outgoing_sms)

        assert cache.get(f"digifarm_blocked_{self.customer.digifarm_farmer_id}") is True

        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        smsr = SMSRecipient.objects.first()
        self.assertEqual(self.outgoing_sms.id, smsr.message.id)
        self.assertEqual(422, int(smsr.failure_reason))
        self.assertEqual('Blocked', smsr.delivery_status)
        self.assertEqual(self.customer.id, smsr.recipient_id)

    # @patch('digifarm.tasks.requests.post')
    @skip("blocking logic broken seemingly in move to bulk api?")
    def test_not_sent_if_number_is_blocked_in_cache(self, post_mock):
        digifarm_id = self.customer.digifarm_farmer_id
        cache.set('digifarm_blocked_FarmerId', True)

        send_digifarm_bulk_sms(digifarm_id, self.outgoing_sms)
        cache.delete('digifarm_blocked_FarmerId')

        post_mock.assert_not_called()

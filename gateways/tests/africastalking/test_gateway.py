from unittest import skip

import responses

from django.conf import settings

from gateways.africastalking import AfricasTalkingGateway

from core.test.cases import TestCase
from sms.tests.factories import OutgoingSMSFactory


class AfricasTalkingGatewayTestCase(TestCase):
    @responses.activate
    def test__send_message_single_recipient_raises_no_exceptions(self):
        responses.add(
            responses.POST,
            settings.AT_SMS_ENDPOINT,
            json={
                'SMSMessageData': {
                    'Recipients': [
                        {
                            'number': '+254711000000',
                            'cost': 'KES 0.0400',
                            'status': 'Success',
                            'messageId': 'ATSid_1'
                        }
                    ]
                }
            }
        )

        msg = OutgoingSMSFactory()
        gateway = AfricasTalkingGateway()
        gateway._send_message(msg, ['+254711000000'], sender='21606')

    @responses.activate
    def test__send_message_multiple_recipient_raises_no_exceptions(self):
        responses.add(
            responses.POST,
            settings.AT_SMS_ENDPOINT,
            json={
                'SMSMessageData': {
                    'Recipients': [
                        {
                            'number': '+254711000000',
                            'cost': 'KES 0.0600',
                            'status': 'Success',
                            'messageId': 'ATSid_1'
                        },
                        {
                            'number': '+254711000001',
                            'cost': 'KES 0.0700',
                            'status': 'Success',
                            'messageId': 'ATSid_2'
                        }
                    ]
                }
            }
        )

        gateway = AfricasTalkingGateway()
        msg = OutgoingSMSFactory()
        gateway._send_message(msg,
                              ['+254711000000', '+254711000001'], sender='21606')

    @skip("Enqueue currently set due to AT response time issues")
    @responses.activate
    def test__send_message_enqueue_not_set_when_below_threshold(self):
        responses.add(
            responses.POST,
            settings.AT_SMS_ENDPOINT,
            json={
                'SMSMessageData': {
                    'Recipients': [
                        {
                            'number': '+254711000000',
                            'cost': 'KES 0.0400',
                            'status': 'Success',
                            'messageId': 'ATSid_1'
                        }
                    ]
                }
            }
        )

        gateway = AfricasTalkingGateway()
        msg = OutgoingSMSFactory()
        gateway._send_message(msg, ['+254711000000'], sender='21606')

        self.assertIn('enqueue=0', responses.calls[0].request.body)

    @responses.activate
    def test__send_message_enqueue_set_at_threshold(self):
        num_recipients = AfricasTalkingGateway.MESSAGE_ENQUEUE_AT
        recipient_numbers = ['+2547' + '{}'.format(n).zfill(8)
                             for n in range(num_recipients)]

        response_json = {
            'SMSMessageData': {
                'Recipients': [
                    {
                        'number': num,
                        'cost': 'KES 0.0600',
                        'status': 'Success',
                        'messageId': 'ATSid_%d' % i
                    } for i, num in enumerate(recipient_numbers)]
            }
        }

        responses.add(
            responses.POST,
            settings.AT_SMS_ENDPOINT,
            json=response_json
        )

        msg = OutgoingSMSFactory()
        gateway = AfricasTalkingGateway()
        gateway._send_message(msg, recipient_numbers, sender='21606')

        self.assertIn('enqueue=1', responses.calls[0].request.body)

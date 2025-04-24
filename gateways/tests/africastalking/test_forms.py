from gateways.africastalking.forms import ATIncomingSMSForm

from core.test.cases import TestCase


class ATIncomingSMSFormTestCase(TestCase):

    def test_can_initialise(self):
        ATIncomingSMSForm()

    def test_form_accepts_valid_data(self):
        f = ATIncomingSMSForm({
            'from': '+254700000000',
            'to': '30606',
            'text': 'hello world',
            'date': '2016-06-17T13:56:03Z',
            'id': 'foo-bar-id',
        })
        self.assertTrue(f.is_valid())

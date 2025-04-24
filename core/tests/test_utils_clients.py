from unittest import mock

from core.test.cases import TestCase

from core.utils.clients import client_setting


class ClientSettingTestCase(TestCase):

    @mock.patch('core.models.Client.sms_shortcode', new_callable=mock.PropertyMock, return_value='fish')
    def test_get_client_setting(self, mock_sms_shortcode):
        out = client_setting('sms_shortcode')
        self.assertEqual(out, 'fish')

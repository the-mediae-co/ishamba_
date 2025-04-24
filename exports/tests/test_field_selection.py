from unittest import skip

from django.contrib.auth import get_user_model
from django.urls import reverse

from django_tenants.test.client import TenantClient as Client

from core.test.cases import TestCase

from exports.models import Export

from ..views import CustomerExportCreateView, IncomingSMSExportCreateView


class ExportFieldSelectionTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant)
        credentials = {
            'username': 'user',
            'password': 'password'
        }
        User = get_user_model()
        User.objects.create_user(**credentials)
        self.client.login(**credentials)

    @skip("Exports is deprecated")
    def test_blank_customer_fields_selection_selects_default(self):
        customer_export_url = reverse('exports:customers')
        self.client.post(customer_export_url, {})

        customer_export = Export.objects.first()
        expected_fields = {
            'fields': list(CustomerExportCreateView.DEFAULT_EXPORTED_FIELDS)
        }
        self.assertEqual(customer_export.fields,
                         expected_fields)

    @skip("Exports is deprecated")
    def test_blank_sms_fields_selection_selects_default(self):
        incoming_sms_url = reverse('exports:incoming-messages')
        self.client.post(incoming_sms_url, {})
        incoming_sms_export = Export.objects.first()
        expected_fields = {
            'fields': list(IncomingSMSExportCreateView.DEFAULT_EXPORTED_FIELDS)
        }
        self.assertEqual(incoming_sms_export.fields,
                         expected_fields)

    @skip("Exports is deprecated")
    def test_customer_field_selection(self):
        customer_fields = {
            'fields': ['name', 'county__name', 'sex']
        }
        customer_export_url = reverse('exports:customers')
        self.client.post(customer_export_url, customer_fields)
        customer_export = Export.objects.first()
        self.assertEqual(customer_export.fields,
                         customer_fields)

    @skip("Exports is deprecated")
    def test_sms_field_selection(self):
        incoming_sms_fields = {
            'fields': ['task__id', 'sender', 'customer__sex']
        }
        incoming_sms_url = reverse('exports:incoming-messages')
        self.client.post(incoming_sms_url, incoming_sms_fields)
        incoming_sms_export = Export.objects.first()
        self.assertEqual(incoming_sms_export.fields,
                         incoming_sms_fields)

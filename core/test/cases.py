from django.db import connection
from django.test import TestCase as Django_TestCase

from django_tenants.test.cases import FastTenantTestCase


# django_tenants (and django-tenant-schemas before that) have a bug where super().setUpClass() is not called.
# Adapted from: https://github.com/django-tenants/django-tenants/issues/813#issuecomment-1220546431
class TestCase(FastTenantTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def tearDownClass(cls):
        Django_TestCase.tearDownClass()
        super().tearDownClass()

    @classmethod
    def setUp(cls):
        connection.set_tenant(cls.tenant)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        # Ensure that fixtures are loaded here
        Django_TestCase.fixtures = cls.fixtures
        Django_TestCase.setUpClass()
        connection.set_tenant(cls.tenant)
        cls.setUpTestData()

    @classmethod
    def setUpTestData(cls):
        connection.set_tenant(cls.tenant)

    @classmethod
    def use_existing_tenant(cls):
        """
        Force update tenant to override existing settings in db
        """
        cls.tenant = cls.setup_tenant(cls.tenant)
        cls.tenant.save()

    @classmethod
    def setup_tenant(cls, tenant):
        """
        Add any additional setting to the tenant before it get saved. This is required if you have
        required fields.

        https://django-tenants.readthedocs.io/en/latest/test.html
        """
        tenant.voice_queue_number = '+254123456780'
        tenant.voice_queue_number_Kenya = '+254710123357'
        tenant.voice_queue_number_Uganda = '+256710123357'
        tenant.voice_dequeue_number = '+254746626911'
        tenant.voice_dequeue_number_Kenya = '+254746626911'
        tenant.voice_dequeue_number_Uganda = '+256746626911'
        tenant.monthly_price = 10.0
        tenant.sms_shortcode = 21606
        tenant.sms_shortcode_Kenya = 21606
        tenant.sms_shortcode_Uganda = 12345
        tenant.mpesa_till_number = 21606
        tenant.mpesa_till_number_Kenya = 21606
        tenant.mpesa_till_number_Uganda = 12345
        tenant.yearly_price = 110.0
        tenant.tip_reports_to = 'foo@bar.com'
        tenant.at_api_key = 'fake_api_key'
        tenant.at_username = 'sandbox'
        tenant.at_sender = 'iShamba'
        tenant.pusher_app_id = '106560'
        tenant.pusher_key = 'fbc04b3d2479e08f8bdc'
        tenant.pusher_secret = 'f964076910d28a82e5cb'

        return tenant

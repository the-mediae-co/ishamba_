from django_tenants.test.client import TenantClient

from callcenters.models import CallCenter
from core.test.cases import TestCase

from django.contrib.auth import get_user_model
from django.urls import reverse


class TestMetrics(TestCase):
    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)

        User = get_user_model()
        self.operator = User.objects.create_user('foo', password='foo')
        self.client.login(username='foo', password='foo')

    def test_logged_in_metrics_work(self):
        resp = self.client.post(
            reverse('core_management_metrics'),
            data={
            }
        )
        self.assertEqual(resp.status_code, 200)

    def test_logged_out_metrics_redirects(self):
        self.client.logout()
        resp = self.client.post(
            reverse('core_management_metrics'),
            data={
            }
        )
        self.assertRedirects(resp, f'/accounts/login/?next=/management/metrics/',
                             status_code=302, target_status_code=200)

    def test_logged_in_date_range_metrics_work(self):
        resp = self.client.post(
            reverse('core_management_metrics'),
            data={
                'start_date': '2019-01-01',
                'end_date': '2019-01-31',
                'submit': 'Update',
            }
        )
        self.assertEqual(resp.status_code, 200)

    def test_logged_in_date_range_and_call_center_metrics_work(self):
        resp = self.client.post(
            reverse('core_management_metrics'),
            data={
                'start_date': '2019-01-01',
                'end_date': '2019-01-31',
                'call_center': CallCenter.objects.first().pk,
                'submit': 'Update',
            }
        )
        self.assertEqual(resp.status_code, 200)

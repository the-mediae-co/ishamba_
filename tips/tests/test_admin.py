from datetime import timedelta
from django_tenants.test.client import TenantClient as Client
from core.test.cases import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from customers.tests.factories import CustomerFactory, CustomerCategoryFactory
from .factories import TipSeriesFactory
from ..models import TipSeries, TipSeriesSubscription, BulkTipSeriesSubscription

User = get_user_model()


class TipAdminTestCase(TestCase):
    def setUp(self):
        super().setUp()
        try:
            self.user = User.objects.get(username='superuser')
        except User.DoesNotExist as e:
            self.user = User.objects.create_superuser('superuser',
                                                      email='foo@bar.baz',
                                                      password='abc123')
        self.client = Client(self.tenant)
        self.client.login(username='superuser', password='abc123')

    def tearDown(self):
        super().tearDown()
        self.user.delete()
        self.client.logout()

    def test_admin_create_bulk_tipseries_subscription_one_customer_works(self):
        category = CustomerCategoryFactory()
        tip_series = TipSeriesFactory()
        commodity = tip_series.commodity
        customer = CustomerFactory(
            blank=True,
            categories=[category],
        )
        start = timezone.now()
        post_data = {
            'categories': [category.id],
            'tip_series': tip_series.id,
            'start': start,
        }
        response = self.client.post(
            reverse('admin:tips_bulktipseriessubscription_add'),
            post_data,
            follow=True
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, TipSeries.objects.count())
        self.assertEqual(1, TipSeriesSubscription.objects.count())
        self.assertEqual(1, BulkTipSeriesSubscription.objects.count())
        tss = TipSeriesSubscription.objects.first()
        self.assertEqual(customer, tss.customer)
        self.assertEqual(tip_series, tss.series)
        self.assertEqual(start, tss.start)
        btss = BulkTipSeriesSubscription.objects.first()
        self.assertEqual(category, btss.categories.first())
        self.assertEqual(tip_series, btss.tip_series)
        self.assertEqual(start, btss.start)

    def test_admin_create_bulk_tipseries_subscription_multiple_customers_works(self):
        category = CustomerCategoryFactory()
        tip_series = TipSeriesFactory()
        commodity = tip_series.commodity
        category_customers = []
        for i in range(5):
            c = CustomerFactory(
                blank=True,
                categories=[category],
            )
            category_customers.append(c)
        non_category_customers = []
        for i in range(5):
            c = CustomerFactory(
                blank=True,
                categories=None,
            )
            non_category_customers.append(c)

        start = timezone.now()
        post_data = {
            'categories': [category.id],
            'tip_series': tip_series.id,
            'start': start,
        }
        response = self.client.post(
            reverse('admin:tips_bulktipseriessubscription_add'),
            post_data,
            follow=True
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, TipSeries.objects.count())
        self.assertEqual(len(category_customers), TipSeriesSubscription.objects.count())
        self.assertEqual(1, BulkTipSeriesSubscription.objects.count())
        for tss in TipSeriesSubscription.objects.all():
            self.assertIn(tss.customer, category_customers)
            self.assertNotIn(tss.customer, non_category_customers)
            self.assertEqual(tip_series, tss.series)
            self.assertEqual(start, tss.start)
        btss = BulkTipSeriesSubscription.objects.first()
        self.assertEqual(category, btss.categories.first())
        self.assertEqual(tip_series, btss.tip_series)
        self.assertEqual(start, btss.start)

    def test_admin_create_bulk_tipseries_subscription_empty_category(self):
        category1 = CustomerCategoryFactory()
        category2 = CustomerCategoryFactory()
        tip_series = TipSeriesFactory()
        commodity = tip_series.commodity
        category_customers = []
        for i in range(2):
            c = CustomerFactory(
                blank=True,
                categories=[category1],
            )
            category_customers.append(c)
        non_category_customers = []
        for i in range(2):
            c = CustomerFactory(
                blank=True,
                categories=None,
            )
            non_category_customers.append(c)

        start = timezone.now()
        post_data = {
            'categories': [category2.id],
            'tip_series': tip_series.id,
            'start': start,
        }
        response = self.client.post(
            reverse('admin:tips_bulktipseriessubscription_add'),
            post_data,
            follow=True
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, TipSeries.objects.count())
        self.assertEqual(0, TipSeriesSubscription.objects.count())
        self.assertEqual(0, BulkTipSeriesSubscription.objects.count())

    def test_admin_create_bulk_tipseries_subscription_long_past_start(self):
        category = CustomerCategoryFactory()
        tip_series = TipSeriesFactory()
        commodity = tip_series.commodity
        customer = CustomerFactory(
            blank=True,
            categories=[category],
        )

        start = timezone.now() - timedelta(days=1000)
        post_data = {
            'categories': [category.id],
            'tip_series': tip_series.id,
            'start': start,
        }
        response = self.client.post(
            reverse('admin:tips_bulktipseriessubscription_add'),
            post_data,
            follow=True
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, TipSeries.objects.count())
        self.assertEqual(0, TipSeriesSubscription.objects.count())
        self.assertEqual(0, BulkTipSeriesSubscription.objects.count())

    def test_admin_create_bulk_tipseries_subscription_long_future_start(self):
        category = CustomerCategoryFactory()
        tip_series = TipSeriesFactory()
        commodity = tip_series.commodity
        customer = CustomerFactory(
            blank=True,
            categories=[category],
        )

        start = timezone.now() + timedelta(days=1000)
        post_data = {
            'categories': [category.id],
            'tip_series': tip_series.id,
            'start': start,
        }
        response = self.client.post(
            reverse('admin:tips_bulktipseriessubscription_add'),
            post_data,
            follow=True
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, TipSeries.objects.count())
        self.assertEqual(0, TipSeriesSubscription.objects.count())
        self.assertEqual(0, BulkTipSeriesSubscription.objects.count())

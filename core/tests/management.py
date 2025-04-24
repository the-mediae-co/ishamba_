import datetime

from django.test import TestCase

from core import constants
from core.tests.utils import create_subscribed_customer
from core.views import get_subscription_rate_chart_data
from customers.models import Customer, Subscription
from payments.models import SubscriptionPeriod, SubscriptionRate


class SubscriptionRateChartTest(TestCase):
    """
    NOTE: These tests are not run (due to filename) as they are completely
    broken and cover depreciated functionality (i.e. customer subscriptions)
    from the free trail based business model.
    """

    def setUp(self):
        super().setUp()
        subscription_period_start_date = datetime.date(2015, 1, 1)

        self.customers = [
            ('+25420000001', datetime.date(2015, 1, 10), datetime.date(2015, 1, 12)),
            ('+25420000002', datetime.date(2015, 1, 10), datetime.date(2015, 2, 10)),
            ('+25420000003', datetime.date(2015, 1, 31), datetime.date(2015, 5, 10)),
            ('+25420000004', datetime.date(2015, 2, 28), datetime.date(2015, 5, 10)),
            ('+25420000005', datetime.date(2015, 3, 10), datetime.date(2015, 4, 10)),
            ('+25420000006', datetime.date(2015, 4, 10), datetime.date(2015, 6, 10)),
        ]

        self.subsequent_subscriptions = [
            ('+25420000001', datetime.date(2015, 4, 10), datetime.date(2015, 8, 12)),  # with a gap though masked by the other Jan starters below
            ('+25420000002', datetime.date(2015, 2, 11), datetime.date(2015, 3, 10)),  # immediate
            ('+25420000003', datetime.date(2015, 5, 11), datetime.date(2015, 6, 10)),  # immediate
            ('+25420000004', datetime.date(2015, 5, 28), datetime.date(2015, 6, 27)),  # with a gap less than a month, should appear subsequent on a monthly resolution
            ('+25420000005', datetime.date(2015, 8, 10), datetime.date(2015, 10, 10)),  # with a large gap
        ]

        subscription_period = SubscriptionPeriod.objects.create(
            start_date=subscription_period_start_date
        )
        SubscriptionRate.objects.create(
            subscription_period=subscription_period,
            months=1,
            amount=80
        )
        SubscriptionRate.objects.create(
            subscription_period=subscription_period,
            months=12,
            amount=800
        )

    def create_customers(self, *indexes):
        if indexes == ():
            indexes = range(len(self.customers))
        for i in indexes:
            customer, subscription = create_subscribed_customer(*self.customers[i])
            setattr(self, 'customer{}'.format(i), customer)
            setattr(self, 'subscription{}'.format(i), subscription)

    def create_subsequent_subscriptions(self, *indexes):
        if indexes == ():
            indexes = range(len(self.subsequent_subscriptions))
        for i in indexes:
            phone, start_date, end_date = self.subsequent_subscriptions[i]
            customer = getattr(self, 'customer{}'.format(i))
            subscription = Subscription.objects.create(customer=customer,
                                                       start_date=start_date,
                                                       end_date=end_date)
            setattr(self, 'subscription{}_subsequent'.format(i), subscription)

    def test_customer_joined_between_queryset_simple(self):
        self.create_customers(0)
        subscriptions = Subscription.objects.customer_joined_between(datetime.datetime(2015, 1, 1), datetime.datetime(2015, 1, 31))
        self.assertIn(self.subscription0, subscriptions)

        customers = Customer.objects.filter(subscription__in=subscriptions)
        self.assertIn(self.customer0, customers)

    def test_customer_joined_between_queryset_all_january(self):
        self.create_customers()
        subscriptions = Subscription.objects.customer_joined_between(datetime.datetime(2015, 1, 1), datetime.datetime(2015, 1, 31))
        self.assertIn(self.subscription0, subscriptions)
        self.assertIn(self.subscription1, subscriptions)
        self.assertIn(self.subscription2, subscriptions)
        self.assertNotIn(self.subscription3, subscriptions)
        self.assertNotIn(self.subscription4, subscriptions)
        self.assertNotIn(self.subscription5, subscriptions)

        customers = Customer.objects.filter(subscription__in=subscriptions)
        self.assertIn(self.customer0, customers)
        self.assertIn(self.customer1, customers)
        self.assertIn(self.customer2, customers)
        self.assertNotIn(self.customer3, customers)
        self.assertNotIn(self.customer4, customers)
        self.assertNotIn(self.customer5, customers)

    def test_customer_joined_between_queryset_all_february(self):
        self.create_customers()
        subscriptions = Subscription.objects.customer_joined_between(datetime.datetime(2015, 2, 1), datetime.datetime(2015, 2, 28))
        self.assertNotIn(self.subscription0, subscriptions)
        self.assertNotIn(self.subscription1, subscriptions)
        self.assertNotIn(self.subscription2, subscriptions)
        self.assertIn(self.subscription3, subscriptions)
        self.assertNotIn(self.subscription4, subscriptions)
        self.assertNotIn(self.subscription5, subscriptions)

        customers = Customer.objects.filter(subscription__in=subscriptions)
        self.assertNotIn(self.customer0, customers)
        self.assertNotIn(self.customer1, customers)
        self.assertNotIn(self.customer2, customers)
        self.assertIn(self.customer3, customers)
        self.assertNotIn(self.customer4, customers)
        self.assertNotIn(self.customer5, customers)

    def test_customer_joined_between_queryset_with_subsequent_subscriptions_february(self):
        self.create_customers()
        self.create_subsequent_subscriptions()
        subscriptions = Subscription.objects.customer_joined_between(datetime.datetime(2015, 2, 1), datetime.datetime(2015, 2, 28))
        self.assertNotIn(self.subscription1, subscriptions)
        self.assertNotIn(self.subscription2, subscriptions)
        self.assertIn(self.subscription3, subscriptions)
        self.assertNotIn(self.subscription4, subscriptions)
        self.assertNotIn(self.subscription5, subscriptions)

        customers = Customer.objects.filter(subscription__in=subscriptions)
        self.assertNotIn(self.subscription0, subscriptions)
        self.assertNotIn(self.customer0, customers)
        self.assertNotIn(self.customer1, customers)
        self.assertNotIn(self.customer2, customers)
        self.assertIn(self.customer3, customers)
        self.assertNotIn(self.customer4, customers)
        self.assertNotIn(self.customer5, customers)

    def test_subscription_rate_chart_trivial(self):
        chartdata = get_subscription_rate_chart_data(
            datetime.date(2015, 1, 1),
            datetime.date(2015, 5, 1),
            constants.DATE_RESOLUTION_MONTHS
        )
        expected_columns = [
            ['01 January', 0, 0, 0, 0, 0],
            ['01 February', 0, 0, 0, 0, 0],
            ['01 March', 0, 0, 0, 0, 0],
            ['01 April', 0, 0, 0, 0, 0],
            ['01 May', 0, 0, 0, 0, 0]
        ]
        self.assertEqual(chartdata['columns'], expected_columns)

    def test_subscription_rate_chart_months(self):
        self.create_customers()
        chartdata = get_subscription_rate_chart_data(
            datetime.date(2015, 1, 1),
            datetime.date(2015, 10, 1),
            constants.DATE_RESOLUTION_MONTHS
        )
        expected_columns = [
            ['01 January', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # nobody joined in the month before 1 January
            ['01 February', 0, 2, 1, 1, 1, 0, 0, 0, 0, 0],  # 3 joined during January, only two lasted to the end of the month, one lasted to mid May
            ['01 March', 0, 0, 1, 1, 1, 0, 0, 0, 0, 0],  # 1 joined in February, lasting until mid May
            ['01 April', 0, 0, 0, 1, 0, 0, 0, 0, 0, 0],  # 1 joined in March, lasting until mid April
            ['01 May', 0, 0, 0, 0, 1, 1, 0, 0, 0, 0],  # 1 joined on 1 April, lasting until mid June
            ['01 June', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # nobody joined from 1 May onwards
            ['01 July', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ['01 August', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ['01 September', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ['01 October', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        ]

        self.assertEqual(chartdata['columns'], expected_columns)

    def test_subscription_rate_chart_renewed_subscriptions(self):
        self.create_customers()
        self.create_subsequent_subscriptions()
        chartdata = get_subscription_rate_chart_data(
            datetime.date(2015, 1, 1),
            datetime.date(2015, 10, 1),
            constants.DATE_RESOLUTION_MONTHS
        )
        expected_columns = [
            #                   J  F  Mr A  My Jn Jy A  S  O
            ['01 January', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # nobody joined in the month before 1 January
            #              0  0  0  0  1  1  1  1          customer 0
            #                   0  1  1                         customer 1
            #                   0  1  1  1  1  1                customer 2
            ['01 February', 0, 2, 2, 1, 2, 2, 1, 1, 0, 0],  # sums of the above three
            ['01 March', 0, 0, 1, 1, 1, 1, 0, 0, 0, 0],  # 1 joined in February, lasting until mid May, extended 1-month immediately after
            ['01 April', 0, 0, 0, 1, 0, 0, 0, 0, 1, 1],  # 1 joined in March, lasting until mid April, extended from mid August to Oct
            ['01 May', 0, 0, 0, 0, 1, 1, 0, 0, 0, 0],  # 1 joined on 1 April, lasting until mid June
            ['01 June', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # nobody joined from 1 May onwards
            ['01 July', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ['01 August', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ['01 September', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ['01 October', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        ]

        self.assertEqual(chartdata['columns'], expected_columns)

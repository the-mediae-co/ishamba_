from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from core.test.cases import TestCase

from ..models import Customer
from subscriptions.models import Subscription
from .factories import (CustomerFactory, SubscriptionFactory,
                        SubscriptionTypeFactory)


class SubscriptionQuerysetTestCase(TestCase):

    def test_permanent(self):
        # By default each customer will have a permanent free subscription
        CustomerFactory.create_batch(10)
        self.assertEqual(Subscription.objects.permanent().count(), 10)

    def test_permanent_with_mix_of_subscriptions(self):
        # By default each customer will have a permanent free subscription
        customers = CustomerFactory.create_batch(5)
        sub_type = SubscriptionTypeFactory()
        # Create an extra non-permanent sub for some
        [SubscriptionFactory(customer=c, type=sub_type) for c in customers[:2]]
        self.assertEqual(Subscription.objects.permanent().count(), 5)

    def test_active_now_with_mix_of_subscriptions(self):
        # By default each customer will have a permanent free subscription
        CustomerFactory.create_batch(5)
        customers = CustomerFactory.create_batch(5)
        sub_type = SubscriptionTypeFactory()
        # Create an extra non-permanent sub for each
        [SubscriptionFactory(customer=c, type=sub_type) for c in customers]

        # Second group of customers should have 2 active subscription
        self.assertEqual(Subscription.objects.active().count(), 15)

    def test_active_after_natural_expiry(self):
        # By default each customer will have a permanent free subscription
        CustomerFactory.create_batch(5)
        customers = CustomerFactory.create_batch(5)
        sub_type = SubscriptionTypeFactory()
        # Create an extra non-permanent sub for each
        [SubscriptionFactory(customer=c, type=sub_type) for c in customers]

        # Second group of customers should only have 1 active subscription
        when = date.today() + relativedelta(years=5)
        self.assertEqual(Subscription.objects.active(date=when).count(), 10)

    def test_active_before_start_date(self):
        # By default each customer will have a permanent free subscription
        customers = CustomerFactory.create_batch(5)
        sub_type = SubscriptionTypeFactory()
        start = date.today() + relativedelta(days=5)
        # Create an extra sub for each, starting in 5 days time
        [SubscriptionFactory(customer=c, start_date=start, type=sub_type)
            for c in customers]

        self.assertEqual(Subscription.objects.active().count(), 5)

    def test_active_after_start_date(self):
        # By default each customer will have a permanent free subscription
        customers = CustomerFactory.create_batch(5)
        sub_type = SubscriptionTypeFactory()
        start = date.today() + relativedelta(days=5)
        # Create an extra sub for each, starting in 5 days time
        [SubscriptionFactory(customer=c, start_date=start, type=sub_type)
            for c in customers]

        when = date.today() + relativedelta(days=10)
        self.assertEqual(Subscription.objects.active(date=when).count(), 10)

    def test_current_by_date_now_with_mix_of_subscriptions(self):
        # By default each customer will have a permanent free subscription
        CustomerFactory.create_batch(5)
        customers = CustomerFactory.create_batch(5)
        sub_type = SubscriptionTypeFactory()
        # Create an extra non-permanent sub for each
        [SubscriptionFactory(customer=c, type=sub_type) for c in customers]

        # Second group of customers should have 2 active subscription
        self.assertEqual(Subscription.objects.current_by_date().count(), 15)

    def test_current_by_date_after_natural_expiry(self):
        # By default each customer will have a permanent free subscription
        CustomerFactory.create_batch(5)
        customers = CustomerFactory.create_batch(5)
        sub_type = SubscriptionTypeFactory()  # premium
        # Create an extra non-permanent sub for each
        [SubscriptionFactory(customer=c, type=sub_type) for c in customers]

        # Second group of customers should only have 1 active subscription (the permanent type)
        when = date.today() + relativedelta(years=5)
        self.assertEqual(Subscription.objects.current_by_date(date=when).count(), 0)

    def test_current_by_date_before_start_date(self):
        # By default each customer will have a permanent free subscription
        customers = CustomerFactory.create_batch(5)
        sub_type = SubscriptionTypeFactory()
        start = date.today() + relativedelta(days=5)
        # Create an extra sub for each, starting in 5 days time
        [SubscriptionFactory(customer=c, start_date=start, type=sub_type)
            for c in customers]

        self.assertEqual(Subscription.objects.current_by_date().count(), 5)

    def test_current_by_date_after_start_date(self):
        # By default each customer will have a permanent free subscription
        customers = CustomerFactory.create_batch(5)
        sub_type = SubscriptionTypeFactory()
        start = date.today() + relativedelta(days=5)
        # Create an extra sub for each, starting in 5 days time
        [SubscriptionFactory(customer=c, start_date=start, type=sub_type)
            for c in customers]

        when = date.today() + relativedelta(days=10)
        self.assertEqual(Subscription.objects.current_by_date(date=when).count(), 10)

    def test_potent_before_start_date(self):
        # By default each customer will have a permanent free subscription
        customers = CustomerFactory.create_batch(5)
        sub_type = SubscriptionTypeFactory()
        start = date.today() + relativedelta(days=5)
        # Create an extra sub for each, starting in 5 days time
        [SubscriptionFactory(customer=c, start_date=start, type=sub_type)
            for c in customers]
        self.assertEqual(Subscription.objects.potent().count(), 10)

    def test_potent_after_expiry(self):
        # By default each customer will have a permanent free subscription
        CustomerFactory.create_batch(5)
        customers = CustomerFactory.create_batch(5)
        sub_type = SubscriptionTypeFactory()
        # Create an extra non-permanent sub for each
        [SubscriptionFactory(customer=c, type=sub_type) for c in customers]

        # Second group of customers should only have 1 active subscription
        when = date.today() + relativedelta(years=5)
        self.assertEqual(Subscription.objects.potent(date=when).count(), 10)


class CustomerQuerysetTestCase(TestCase):

    def test_can_access_call_centre(self):
        customer = CustomerFactory()
        qs = Customer.objects.can_access_call_centre()
        self.assertEqual(list(qs.values_list('pk', flat=True)), [customer.pk])

    @patch('customers.managers.client_setting')
    def test_can_access_restricted_call_centre_unregistered(self, mocked_client_setting):
        mocked_client_setting.return_value = True
        CustomerFactory(unregistered=True)
        qs = Customer.objects.can_access_call_centre()
        self.assertEqual(list(qs.values_list('pk', flat=True)), [])

    @patch('customers.managers.client_setting')
    def test_can_access_unrestricted_call_centre_unregistered(self, mocked_client_setting):
        mocked_client_setting.return_value = False
        customer = CustomerFactory(unregistered=True)
        qs = Customer.objects.can_access_call_centre()
        self.assertEqual(list(qs.values_list('pk', flat=True)), [customer.pk])

    @patch('customers.managers.client_setting')
    def test_can_access_restricted_call_centre_registered(self, mocked_client_setting):
        mocked_client_setting.return_value = True
        customer = CustomerFactory(unregistered=False)
        qs = Customer.objects.can_access_call_centre()
        self.assertEqual([customer.pk], list(qs.values_list('pk', flat=True)))

    @patch('customers.managers.client_setting')
    def test_can_access_unrestricted_call_centre_registered(self, mocked_client_setting):
        mocked_client_setting.return_value = False
        customer = CustomerFactory(unregistered=False)
        qs = Customer.objects.can_access_call_centre()
        self.assertEqual([customer.pk], list(qs.values_list('pk', flat=True)))

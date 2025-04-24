from django.contrib.auth import get_user_model

from core.test.cases import TestCase
from customers.models import Customer, CustomerPhone

from .factories import TipSeriesSubscriptionFactory

User = get_user_model()


class TipSeriesActionsTest(TestCase):

    def setUp(self):
        super().setUp()
        # we don't use CustomerFactory because it adds subscriptions
        # which would make these tests a bit harder to understand
        self.customer = Customer.objects.create(name='Customer')
        phone = CustomerPhone.objects.create(number='+254720123456', is_main=True, customer=self.customer)

    def test_recording_market_subscriptions(self):
        subscription = TipSeriesSubscriptionFactory(
            customer=self.customer
        )

        actions = self.customer.actor_actions.all()

        self.assertEqual(len(actions), 1)

        action = actions[0]
        self.assertEqual(action.target, subscription.series)

    def test_recording_market_unsubscription(self):
        subscription = TipSeriesSubscriptionFactory(
            customer=self.customer
        )
        subscription.delete()

        actions = self.customer.actor_actions.all()

        self.assertEqual(len(actions), 2)

        action = actions[1]
        self.assertEqual(action.target, subscription.series)

    def test_recording_subscriptions_by_agent(self):
        user = User.objects.create(username='user')
        subscription = TipSeriesSubscriptionFactory(
            customer=self.customer,
            creator_id=user.id
        )
        subscription.last_editor_id = user.id
        subscription.delete()

        actions = self.customer.actor_actions.all()
        for action in actions:
            self.assertEqual(action.data['agent_id'], user.id)

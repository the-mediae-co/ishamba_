from django.contrib.auth import get_user_model
from django.utils.timezone import now

from core.test.cases import TestCase

import calls.models
from customers.tests.factories import CustomerFactory


class TestPreviousCallNumberTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.subscribed_customer = CustomerFactory()

    def test_previous_call_number(self):
        first_call = calls.models.Call.objects.create(
            customer=self.subscribed_customer,
            caller_number=self.subscribed_customer.main_phone
        )
        self.assertEqual(first_call.previous_calls_number, 0)

        second_call = calls.models.Call.objects.create(
            customer=self.subscribed_customer,
            caller_number=self.subscribed_customer.main_phone
        )
        self.assertEqual(second_call.previous_calls_number, 1)


class TestPhoneCurrentOperatorTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.phone = calls.models.CallCenterPhone.objects.create(phone_number='+254722111111')
        self.operator = get_user_model().objects.create(username='operator')

    def test_no_operator_without_session(self):
        self.assertEqual(self.phone.current_operator, None)

    def test_returns_operator_when_active_session(self):
        calls.models.PusherSession.objects.create(
            call_center_phone=self.phone,
            operator=self.operator,
            pusher_session_key='111',
        )
        self.assertEqual(self.phone.current_operator, self.operator)

    def test_returns_correct_operator(self):
        calls.models.PusherSession.objects.create(
            call_center_phone=self.phone,
            operator=self.operator,
            pusher_session_key='111',
        )

        other_operator = get_user_model().objects.create(username='other_operator')
        calls.models.PusherSession.objects.create(
            call_center_phone=self.phone,
            operator=other_operator,
            pusher_session_key='11122',
            finished_on=now()
        )

        self.assertEqual(self.phone.current_operator, self.operator)


class TestEmptyCallCenter(TestCase):
    def setUp(self):
        super().setUp()
        self.phone = calls.models.CallCenterPhone.objects.create(phone_number='+254722111111')
        self.operator = get_user_model().objects.create(username='operator')

    def test_empty_call_center(self):
        self.assertEqual(calls.models.PusherSession.objects.empty_call_center(), True)

    def test_call_center_has_operator(self):
        calls.models.PusherSession.objects.create(
            call_center_phone=self.phone,
            operator=self.operator,
            pusher_session_key='11122',
        )
        self.assertEqual(calls.models.PusherSession.objects.empty_call_center(), False)

    def test_call_center_has_finished_operator(self):
        calls.models.PusherSession.objects.create(
            call_center_phone=self.phone,
            operator=self.operator,
            pusher_session_key='11122',
            finished_on=now()
        )
        self.assertEqual(calls.models.PusherSession.objects.empty_call_center(), True)

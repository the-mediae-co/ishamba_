from django.contrib.contenttypes.models import ContentType
from django.db import connection

from core.test.cases import TestCase

from actstream.models import Action
from gateways.africastalking.testing import activate_success_response

from customers.models import Customer, CustomerPhone
from customers.tests.factories import CustomerFactory

from ..models import OutgoingSMS
from ..signals.handlers import handle_outgoing_sms
from ..signals.signals import sms_sent
from .factories import OutgoingSMSFactory, IncomingSMSFactory


class SMSActionsTest(TestCase):

    def setUp(self):
        super().setUp()
        # self.customer = CustomerFactory(blank=True)
        # CustomerFactory fires off several Actions to record commodity subscriptions, etc.
        # Manually creating a customer is cleaner and creates no additional Actions.
        self.customer = Customer.objects.create(name='Customer')
        self.phone = CustomerPhone.objects.create(number='+254700100200', is_main=True, customer=self.customer)

        # When content types are fetched they are cached and this can make query
        # counting unpredictable. We need the cache to be empty at the beginning of
        # the test.
        ContentType.objects.clear_cache()

    def test_incoming_sms_recording(self):
        sms = IncomingSMSFactory(
            customer=self.customer
        )

        actions = self.customer.actor_actions.all()

        self.assertEqual(len(actions), 1)

        action = actions[0]

        self.assertEqual(action.action_object, sms)
        self.assertEqual(action.timestamp, sms.at)

    @activate_success_response
    def test_outgoing_sms_recording(self):
        sms = OutgoingSMSFactory()

        sms.send(TestCase.get_test_schema_name(), [self.customer], sender='iShamba')

        actions = self.customer.actor_actions.all()
        self.assertEqual(len(actions), 1)

        action = actions[0]
        self.assertEqual(action.action_object, sms)

    @activate_success_response
    def test_multiple_outgoing_sms_recording(self):
        beginning_count = Action.objects.count()
        customer1 = Customer.objects.create(name='1')
        CustomerPhone.objects.create(number='+254700123123', is_main=True, customer=customer1)
        customer2 = Customer.objects.create(name='2')
        CustomerPhone.objects.create(number='+254700123456', is_main=True, customer=customer2)

        sms = OutgoingSMSFactory()
        sms.send(TestCase.get_test_schema_name(), [customer1, customer2], sender='iShamba')

        actions_count = Action.objects.count()
        self.assertEqual(actions_count, beginning_count + 2)

    @activate_success_response
    def test_incoming_sms_query_count(self):
        # each 'action' recording is expected to do 6 queries:
        # 1. SELECT (1) AS "a" FROM "customers_customerphone" WHERE "customers_customerphone"."customer_id" = 7 LIMIT 1
        # 2. SELECT "customers_customerphone"."id", "customers_customerphone"."number", "customers_customerphone"."is_main", "customers_customerphone"."customer_id" FROM "customers_customerphone" WHERE ("customers_customerphone"."customer_id" = 7 AND "customers_customerphone"."is_main") LIMIT 21
        # 3. INSERT INTO "sms_incomingsms" ("created", "creator_id", "last_updated", "last_editor_id", "at", "sender", "recipient", "text", "gateway", "gateway_id", "customer_id", "customer_created") VALUES ('2022-08-31T20:32:13.466103+00:00'::timestamptz, NULL, '2022-08-31T20:32:13.466113+00:00'::timestamptz, NULL, '2022-08-31T20:32:13.465880+00:00'::timestamptz, '+254700100200', '12345', '', 0, '80c55ce4-16b2-43e5-b643-6bd4090c7c25', 7, true) RETURNING "sms_incomingsms"."id"
        # 4. SELECT "django_content_type"."id", "django_content_type"."app_label", "django_content_type"."model" FROM "django_content_type" WHERE ("django_content_type"."app_label" = 'customers' AND "django_content_type"."model" = 'customer') LIMIT 21
        # 5. SELECT "django_content_type"."id", "django_content_type"."app_label", "django_content_type"."model" FROM "django_content_type" WHERE ("django_content_type"."app_label" = 'sms' AND "django_content_type"."model" = 'incomingsms') LIMIT 21
        # 6. INSERT INTO "actstream_action" ("actor_content_type_id", "actor_object_id", "verb", "description", "target_content_type_id", "target_object_id", "action_object_content_type_id", "action_object_object_id", "timestamp", "public", "data") VALUES (21, '7', 'sent sms', NULL, NULL, NULL, 48, '1', '2022-08-31T20:32:13.465880+00:00'::timestamptz, true, NULL) RETURNING "actstream_action"."id"
        with self.assertNumQueries(6):
            IncomingSMSFactory(
                customer=self.customer
            )

        # The first 2 content type queries are not repeated after the first time:
        # 1. SELECT (1) AS "a" FROM "customers_customerphone" WHERE "customers_customerphone"."customer_id" = 69 LIMIT 1
        # 2. SELECT "customers_customerphone"."id", "customers_customerphone"."number", "customers_customerphone"."is_main", "customers_customerphone"."customer_id" FROM "customers_customerphone" WHERE ("customers_customerphone"."customer_id" = 69 AND "customers_customerphone"."is_main") LIMIT 21
        # 3. INSERT INTO "sms_incomingsms" ("created", "creator_id", "last_updated", "last_editor_id", "at", "sender", "recipient", "text", "gateway", "gateway_id", "customer_id", "customer_created") VALUES ('2022-08-31T20:37:33.096571+00:00'::timestamptz, NULL, '2022-08-31T20:37:33.096581+00:00'::timestamptz, NULL, '2022-08-31T20:37:33.096420+00:00'::timestamptz, '+254700100200', '12345', '', 0, '3e597aed-bd61-43e0-a32f-05b300d59de7', 69, true) RETURNING "sms_incomingsms"."id"
        # 4. INSERT INTO "actstream_action" ("actor_content_type_id", "actor_object_id", "verb", "description", "target_content_type_id", "target_object_id", "action_object_content_type_id", "action_object_object_id", "timestamp", "public", "data") VALUES (21, '69', 'sent sms', NULL, NULL, NULL, 48, '4', '2022-08-31T20:37:33.096420+00:00'::timestamptz, true, NULL) RETURNING "actstream_action"."id"
        with self.assertNumQueries(4):
            # 2 queries here. Insert sms and Insert action
            IncomingSMSFactory(
                customer=self.customer
            )

    @activate_success_response
    def test_outgoing_sms_query_counts(self):
        # The handler that records the action performs the following additional queries
        # 1 query to get the sms recipient IDs
        # 1 query to get the Customer ContentType
        # 1 query to create actions for all customers
        # 1 query to update time_sent

        EXPECTED_ADDITIONAL_QUERIES = 4

        # the type of sms does not matter

        def outgoing_sms_query_test(num_customers):
            _ = [CustomerFactory() for x in range(num_customers)]
            customers = Customer.objects.all()

            sms = OutgoingSMSFactory()
            unrecorded_sms = OutgoingSMSFactory()

            ContentType.objects.clear_cache()
            with self.settings(DEBUG=True):
                # Count the queries performed if sms is sent and no action
                # is recorded. This count is used to determine how many
                # additional queries the action recording code makes
                sms_sent.disconnect(sender=OutgoingSMS,
                                    dispatch_uid="outgoing_sms_sent")

                queries_before = len(connection.queries)
                unrecorded_sms.send(TestCase.get_test_schema_name(), customers, sender='iShamba', send_sms=False)
                query_count_without_action = len(connection.queries) - queries_before

                sms_sent.connect(handle_outgoing_sms,
                                 sender=OutgoingSMS,
                                 dispatch_uid="outgoing_sms_sent")

            ContentType.objects.clear_cache()
            num_queries = query_count_without_action + EXPECTED_ADDITIONAL_QUERIES

            # recreate the queryset, since previous one may have gotten evaluated, affecting number of queries
            customers = Customer.objects.all()
            with self.assertNumQueries(num_queries):
                sms.send(TestCase.get_test_schema_name(), customers, sender='iShamba', send_sms=False)

        for x in range(1, 11):
            outgoing_sms_query_test(x)

    @activate_success_response
    def test_actions_recorded_once_per_customer_per_sms(self):
        beginning_count = Action.objects.count()
        customer1 = Customer.objects.create(name='Customer1')
        customer2 = Customer.objects.create(name='Customer2')
        CustomerPhone.objects.create(number='+254700123456', is_main=True, customer=customer1)
        CustomerPhone.objects.create(number='+254700654321', is_main=True, customer=customer2)

        sms = OutgoingSMSFactory()
        sms.send(TestCase.get_test_schema_name(), customer1, sender='iShamba', send_sms=False)

        self.assertEqual(Action.objects.count(), beginning_count + 1)

        sms.send(TestCase.get_test_schema_name(), customer2, sender='iShamba', send_sms=False)

        self.assertEqual(Action.objects.count(), beginning_count + 2)

        sms.send(TestCase.get_test_schema_name(), [customer1, customer2], sender='iShamba', send_sms=False)

        self.assertEqual(Action.objects.count(), beginning_count + 2)

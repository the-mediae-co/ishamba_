from datetime import datetime, time, timedelta, timezone
from unittest import skip
from unittest.mock import ANY, call, patch

from django.conf import settings
from django.test import override_settings
from django.utils.timezone import make_aware

from agri.constants import SUBSCRIPTION_FLAG
from agri.tests.factories import CommodityFactory
from core.constants import LANGUAGES
from core.test.cases import TestCase
from customers.models import CustomerCommodity
from customers.tests.factories import CustomerFactory
from gateways.africastalking.testing import activate_success_response
from sms.constants import OUTGOING_SMS_TYPE
from sms.models.outgoing import OutgoingSMS, SMSRecipient
from world.models import Border

from .. import models, tasks
from . import factories


def Border1Factory(varied=False):
    if varied:
        # Murang'a causes problems for self.assertContains, so exclude it
        return Border.kenya_counties.exclude(name__contains='Murang\'a').order_by('?').first()
    else:
        return Border.objects.get(country='Kenya', level=1, name='Nairobi')


class SendScheduledTipsTestCase(TestCase):

    @patch('tips.tasks.send_tips_for_commodity.apply_async')
    def test_subtasks_called(self, mocked_subtask):
        all_tips = factories.TipFactory.create_batch(5)
        all_commodities = [tip.commodity for tip in all_tips]
        tasks.send_scheduled_tips()

        calls = [
            call(args=[TestCase.get_test_schema_name(), s.pk],
                 kwargs={"tips_for": None, "report_only": False})
            for s in all_commodities]
        mocked_subtask.assert_has_calls(calls, any_order=True)


class SendTipsForCommodityTestCase(TestCase):
    @patch('tips.tasks.send_message.delay')
    def test_sends_due_tip(self, mocked_send_message):
        commodity = CommodityFactory()
        customer = CustomerFactory()

        customer_commodity = CustomerCommodity.objects.update_or_create(
            customer=customer,
            commodity=commodity,
            defaults={'subscription_flag': SUBSCRIPTION_FLAG.FREEMIUM}
        )

        tip_season = factories.TipSeasonFactory(commodity=commodity, customer_filters={'border3': [customer.border3.pk]})
        tip = factories.TipFactory(commodity=commodity)
        tip_translation = factories.TipTranslationFactory(tip=tip, language=customer.preferred_language)

        self.assertEqual(OutgoingSMS.objects.count(), 0)

        tasks.send_tips_for_commodity(
            TestCase.get_test_schema_name(),
            commodity.pk,
            tips_for=tip_season.start_date + tip.delay)

        self.assertEqual(OutgoingSMS.objects.count(), 1, "should create one message to send")
        self.assertTrue(mocked_send_message.called)

    @patch('tips.tasks.send_message.delay')
    def test_sends_due_tip_in_multiple_languages(self, mocked_send_message):
        commodity = CommodityFactory()
        customer = CustomerFactory(preferred_language=LANGUAGES.KISWAHILI)
        customer2 = CustomerFactory(preferred_language=LANGUAGES.ENGLISH)

        CustomerCommodity.objects.update_or_create(
            customer=customer,
            commodity=commodity,
            defaults={'subscription_flag': SUBSCRIPTION_FLAG.FREEMIUM}
        )
        CustomerCommodity.objects.update_or_create(
            customer=customer2,
            commodity=commodity,
            defaults={'subscription_flag': SUBSCRIPTION_FLAG.FREEMIUM}
        )

        tip_season = factories.TipSeasonFactory(commodity=commodity, customer_filters={'border3': [customer.border3.pk, customer2.border3.pk]})
        tip = factories.TipFactory(commodity=commodity)
        tip_translation = factories.TipTranslationFactory(tip=tip, language=customer.preferred_language)
        tip_translation = factories.TipTranslationFactory(tip=tip, language=customer2.preferred_language)

        self.assertEqual(OutgoingSMS.objects.count(), 0)

        tasks.send_tips_for_commodity(
            TestCase.get_test_schema_name(),
            commodity.pk,
            tips_for=tip_season.start_date + tip.delay)

        self.assertEqual(OutgoingSMS.objects.count(), 2, "should create a distinctm essage per language")
        self.assertEqual(mocked_send_message.call_count, 2)


    @patch('tips.tasks.send_message.delay')
    def test_sends_due_tips_for_different_border3s(self, mocked_send_message):
        commodity = CommodityFactory()

        customer_ward1 = Border.kenya_wards.order_by('?').first()
        customer_ward2 = Border.kenya_wards.exclude(pk=customer_ward1.pk).order_by('?').first()

        customer = CustomerFactory(preferred_language=LANGUAGES.ENGLISH, border3=customer_ward1)
        customer2 = CustomerFactory(preferred_language=LANGUAGES.ENGLISH, border3=customer_ward2)

        CustomerCommodity.objects.update_or_create(
            customer=customer,
            commodity=commodity,
            defaults={'subscription_flag': SUBSCRIPTION_FLAG.FREEMIUM}
        )
        CustomerCommodity.objects.update_or_create(
            customer=customer2,
            commodity=commodity,
            defaults={'subscription_flag': SUBSCRIPTION_FLAG.FREEMIUM}
        )

        # Two different TipSeasons for the different wards with different planting dates.
        tip_season = factories.TipSeasonFactory(commodity=commodity, customer_filters={'border3': [customer_ward1.pk]})
        tip_season2 = factories.TipSeasonFactory(commodity=commodity, customer_filters={'border3': [customer_ward2.pk]},
                                                 start_date=tip_season.start_date + timedelta(days=1))

        tip = factories.TipFactory(commodity=commodity)
        tip_translation = factories.TipTranslationFactory(tip=tip, language=customer.preferred_language)

        self.assertEqual(OutgoingSMS.objects.count(), 0)

        tasks.send_tips_for_commodity(
            TestCase.get_test_schema_name(),
            commodity.pk,
            tips_for=tip_season.start_date + tip.delay)

        self.assertEqual(OutgoingSMS.objects.count(), 1, "should create a message for customer1 whose county is in the earlier TipSeason")
        self.assertEqual(mocked_send_message.call_count, 1)
        mocked_send_message.assert_called_once_with(ANY, recipient_ids=[customer.pk], sender="iShamba")

        tasks.send_tips_for_commodity(
            TestCase.get_test_schema_name(),
            commodity.pk,
            tips_for=tip_season2.start_date + tip.delay)

        self.assertEqual(OutgoingSMS.objects.count(), 2, "should create an additional message for customer2")
        mocked_send_message.assert_called_with(ANY, recipient_ids=[customer2.pk], sender="iShamba")

    @patch('tips.tasks.send_message.delay')
    def test_no_tips_due(self, mocked_send_message):
        commodity = CommodityFactory()
        customer = CustomerFactory()

        customer_commodity = CustomerCommodity.objects.update_or_create(
            customer=customer,
            commodity=commodity,
            defaults={'subscription_flag': SUBSCRIPTION_FLAG.FREEMIUM}
        )

        tip_season = factories.TipSeasonFactory(commodity=commodity, customer_filters={'border3': [customer.border3.pk]})
        tip = factories.TipFactory(commodity=commodity)
        tip_translation = factories.TipTranslationFactory(tip=tip, language=customer.preferred_language)

        tasks.send_tips_for_commodity(
            TestCase.get_test_schema_name(),
            commodity.pk,
            tips_for=tip_season.start_date + tip.delay - timedelta(days=1)) # send tips before the tip delay has expired

        mocked_send_message.assert_not_called()
        self.assertEqual(OutgoingSMS.objects.count(), 0)

    @activate_success_response
    def test_idempotency(self):
        commodity = CommodityFactory()
        customer = CustomerFactory()

        customer_commodity = CustomerCommodity.objects.update_or_create(
            customer=customer,
            commodity=commodity,
            defaults={'subscription_flag': SUBSCRIPTION_FLAG.FREEMIUM}
        )

        tip_season = factories.TipSeasonFactory(commodity=commodity, customer_filters={'border3': [customer.border3.pk]})
        tip = factories.TipFactory(commodity=commodity)
        tip_translation = factories.TipTranslationFactory(tip=tip, language=customer.preferred_language)

        self.assertEqual(OutgoingSMS.objects.count(), 0)

        tasks.send_tips_for_commodity(
            TestCase.get_test_schema_name(),
            commodity.pk,
            tips_for=tip_season.start_date + tip.delay)

        self.assertEqual(OutgoingSMS.objects.count(), 1, "should create one outgoing message")

        self.assertEqual(SMSRecipient.objects.count(), 1, "should send that message to customer")

        # send again
        tasks.send_tips_for_commodity(
            TestCase.get_test_schema_name(),
            commodity.pk,
            tips_for=tip_season.start_date + tip.delay)

        self.assertEqual(SMSRecipient.objects.count(), 1, "should still only be one recipient")


@skip("replaced by above tests for new implementation")
class SendTipsForSeriesTestCase(TestCase):

    @patch('tips.tasks.send_message')
    def test_no_tips(self, mocked_send_tip):
        s = factories.TipSeriesFactory()
        tasks.send_tips_for_commodity(TestCase.get_test_schema_name(), s.commodity.pk)
        mocked_send_tip.delay.assert_not_called()

    @patch('tips.tasks.send_tip')
    def test_no_tips_due(self, mocked_send_tip):
        series = factories.TipSeriesFactory()
        factories.TipSeriesSubscriptionFactory(series=series)
        # Defaults to 3 days delay, so shouldn't be sent
        factories.TipFactory(series=series, border1=None)

        tasks.send_tips_for_commodity(TestCase.get_test_schema_name(), series.commodity.pk)
        mocked_send_tip.delay.assert_not_called()

    @patch('tips.tasks.send_tip')
    def test_send_due_tip(self, mocked_send_tip):
        series = factories.TipSeriesFactory()
        start = make_aware(datetime(2017, 2, 20, 0, 0), timezone.utc)
        when = start + timedelta(days=3)
        sub = factories.TipSeriesSubscriptionFactory(series=series, start=start)
        tip = factories.TipFactory(series=series, border1=None)

        # Set to run in 3 days from the start date
        tasks.send_tips_for_commodity(TestCase.get_test_schema_name(), series.commodity.pk, tips_for=when)
        mocked_send_tip.delay.assert_called_once_with(TestCase.get_test_schema_name(), tip.pk, sub.pk)

    @patch('tips.tasks.send_tip')
    def test_border1_tips(self, mocked_send_tip):
        series = factories.TipSeriesFactory()
        start = make_aware(datetime(2017, 2, 20, 0, 0), timezone.utc)
        when = start + timedelta(days=3)
        border1 = Border1Factory(varied=True)
        border2 = Border1Factory(varied=True)
        # We need the borders to be different
        while border2 == border1:
            border2 = Border1Factory(varied=True)
        self.assertNotEqual(border1, border2)  # I suspect this is why the test case occasionally fails
        customer = CustomerFactory(border1=border1)
        sub = factories.TipSeriesSubscriptionFactory(series=series, start=start, customer=customer)
        tip1 = factories.TipFactory(series=series, border1=border1)
        translation1 = factories.TipTranslationFactory(tip=tip1)
        tip2 = factories.TipFactory(series=series, border1=border2)
        translation2 = factories.TipTranslationFactory(tip=tip2)
        tip3 = factories.TipFactory(series=series, border1=None)
        translation3 = factories.TipTranslationFactory(tip=tip3)

        tasks.send_tips_for_commodity(TestCase.get_test_schema_name(), series.commodity.pk, tips_for=when)

        calls = [
            call(TestCase.get_test_schema_name(), tip1.pk, sub.pk),
            call(TestCase.get_test_schema_name(), tip3.pk, sub.pk),
        ]
        # for c in calls:
        #     self.assertIn(c, mocked_send_tip.delay.mock_calls)
        mocked_send_tip.delay.assert_has_calls(calls)

    @patch('sms.tasks.send_message')
    def test_tip_languages(self, mocked_send_tip):
        series = factories.TipSeriesFactory()
        start = make_aware(datetime(2017, 2, 20, 0, 0), timezone.utc)
        when = start + timedelta(days=3)
        border1 = Border1Factory(varied=True)
        border2 = Border1Factory(varied=True)
        # We need the borders to be different
        while border2 == border1:
            border2 = Border1Factory(varied=True)
        customer1 = CustomerFactory(border1=border1, preferred_language=LANGUAGES.ENGLISH.value)
        customer2 = CustomerFactory(border1=border1, preferred_language=LANGUAGES.KISWAHILI.value)
        sub1 = factories.TipSeriesSubscriptionFactory(series=series, start=start, customer=customer1)
        sub2 = factories.TipSeriesSubscriptionFactory(series=series, start=start, customer=customer2)
        tip1 = factories.TipFactory(series=series, border1=border1)
        translation1_eng = factories.TipTranslationFactory(tip=tip1, language='eng')
        translation1_swa = factories.TipTranslationFactory(tip=tip1, language='swa')
        tip2 = factories.TipFactory(series=series, border1=border2)
        translation2_eng = factories.TipTranslationFactory(tip=tip2, language='eng')
        translation2_swa = factories.TipTranslationFactory(tip=tip2, language='swa')
        tip3 = factories.TipFactory(series=series, border1=None)
        translation3_eng = factories.TipTranslationFactory(tip=tip3, language='eng')
        translation3_swa = factories.TipTranslationFactory(tip=tip3, language='swa')

        tasks.send_tips_for_commodity(TestCase.get_test_schema_name(), series.commodity.pk, tips_for=when)

        calls = [
            call(TestCase.get_test_schema_name(), translation1_eng.text, customer1.pk, OUTGOING_SMS_TYPE.AGRI_TIP, sender='iShamba', extra={'tip_id': tip1.id, 'subscription_id': sub1.id}),
            call(TestCase.get_test_schema_name(), translation1_swa.text, customer2.pk, OUTGOING_SMS_TYPE.AGRI_TIP, sender='iShamba', extra={'tip_id': tip1.id, 'subscription_id': sub2.id}),
            call(TestCase.get_test_schema_name(), translation3_eng.text, customer1.pk, OUTGOING_SMS_TYPE.AGRI_TIP, sender='iShamba', extra={'tip_id': tip3.id, 'subscription_id': sub1.id}),
            call(TestCase.get_test_schema_name(), translation3_swa.text, customer2.pk, OUTGOING_SMS_TYPE.AGRI_TIP, sender='iShamba', extra={'tip_id': tip3.id, 'subscription_id': sub2.id}),
        ]
        # The order of the calls can vary, so mocked_send_tip.assert_has_calls doesn't always work
        for c in calls:
            self.assertIn(c, mocked_send_tip.mock_calls)
        # mocked_send_tip.assert_has_calls(calls)


@skip("send tip removed")
class SendTipTestCase(TestCase):

    @patch('sms.tasks.send_message')
    def test_sending(self, mocked_send_message):
        series = factories.TipSeriesFactory()
        sub = factories.TipSeriesSubscriptionFactory(series=series)
        tip = factories.TipFactory(series=series, border1=None)
        translation = factories.TipTranslationFactory(tip=tip)

        tasks.send_tip(TestCase.get_test_schema_name(), tip.pk, sub.pk)
        self.assertEqual(models.TipSent.objects.count(), 1)

        sent = models.TipSent.objects.first()
        self.assertEqual(sent.tip, tip)
        self.assertEqual(sent.subscription, sub)

        mocked_send_message.assert_called_once_with(TestCase.get_test_schema_name(),
                                                    translation.text,
                                                    sub.customer.pk,
                                                    OUTGOING_SMS_TYPE.AGRI_TIP,
                                                    sender=settings.SMS_SENDER_AGRITIP,
                                                    extra={'tip_id': tip.pk, 'subscription_id': sub.pk})

    @patch('sms.tasks.send_message')
    def test_idempotency(self, mocked_send_message):
        series = factories.TipSeriesFactory()
        sub = factories.TipSeriesSubscriptionFactory(series=series)
        tip = factories.TipFactory(series=series, border1=None)
        translation = factories.TipTranslationFactory(tip=tip)

        tasks.send_tip(TestCase.get_test_schema_name(), tip.pk, sub.pk)
        tasks.send_tip(TestCase.get_test_schema_name(), tip.pk, sub.pk)
        # Second run shouldn't do anything, so only 1 message should be sent
        mocked_send_message.assert_called_once()

    @patch('sms.tasks.send_message')
    def test_only_send_to_active_customers(self, mocked_send_message):
        series = factories.TipSeriesFactory()
        c = CustomerFactory(has_requested_stop=True)
        sub = factories.TipSeriesSubscriptionFactory(series=series, customer=c)
        tip = factories.TipFactory(series=series, border1=None)
        translation = factories.TipTranslationFactory(tip=tip)

        tasks.send_tip(TestCase.get_test_schema_name(), tip.pk, sub.pk)
        mocked_send_message.assert_not_called()


@skip("Ending series subscriptions functionality removed")
class EndSeriesSubscriptionsTestCase(TestCase):

    @patch('sms.tasks.send_message')
    def test_no_matches(self, mocked_send_message):
        tasks.end_series_subscriptions()
        mocked_send_message.assert_not_called()

    @patch('sms.tasks.send_message')
    def test_ignore_subscriptions_with_no_tipsent(self, mocked_send_message):
        end = make_aware(datetime(2017, 2, 24, 1, 0), timezone.utc)

        series = factories.TipSeriesFactory()
        sub = factories.TipSeriesSubscriptionFactory(series=series)
        factories.TipFactory(series=series, delay=timedelta(days=6))

        tasks.end_series_subscriptions(expire_after=end)

        self.assertFalse(sub.ended)
        mocked_send_message.assert_not_called()

    @patch('sms.tasks.send_message')
    def test_ignore_subscriptions_with_not_last_tipsent(self, mocked_send_message):
        start = make_aware(datetime(2017, 2, 20, 0, 0), timezone.utc)
        end = make_aware(datetime(2017, 2, 24, 1, 0), timezone.utc)

        series = factories.TipSeriesFactory()
        sub = factories.TipSeriesSubscriptionFactory(series=series, start=start)
        factories.TipFactory(series=series, delay=timedelta(days=3))
        factories.TipFactory(series=series, delay=timedelta(days=5))

        tasks.end_series_subscriptions(expire_after=end)

        sub.refresh_from_db()
        self.assertFalse(sub.ended)
        mocked_send_message.assert_not_called()

    @override_settings(ENFORCE_BLACKOUT_HOURS=False)
    @patch('sms.tasks.send_message')
    def test_end_subscriptions_without_blackout(self, mocked_send_message):
        start = make_aware(datetime(2017, 2, 20, 0, 0), timezone.utc)
        end = make_aware(datetime(2017, 2, 25, 1, 0), timezone.utc)

        series = factories.TipSeriesFactory()
        sub = factories.TipSeriesSubscriptionFactory(series=series, start=start)
        factories.TipFactory(series=series, delay=timedelta(days=5))

        tasks.end_series_subscriptions(expire_after=end)

        # Default manager filters out ended subscriptions
        self.assertTrue(models.TipSeriesSubscription._base_manager.get(pk=sub.pk).ended)
        mocked_send_message.delay.assert_called_once_with(TestCase.get_test_schema_name(),
                                                          series.end_message,
                                                          sub.customer_id,
                                                          OUTGOING_SMS_TYPE.SUBSCRIPTION_NOTIFICATION,
                                                          sender=settings.SMS_SENDER_AGRITIP,
                                                          extra={'subscription_id': sub.pk})

    @override_settings(ENFORCE_BLACKOUT_HOURS=True)
    @patch('sms.tasks.send_message')
    def test_end_subscriptions_with_blackout_morning(self, mocked_send_message):
        start = make_aware(datetime(2017, 2, 20, 4, 0))
        end = make_aware(datetime(2017, 2, 25, 5, 0))

        series = factories.TipSeriesFactory()
        sub = factories.TipSeriesSubscriptionFactory(series=series, start=start)
        factories.TipFactory(series=series, delay=timedelta(days=5))

        # mimic an execution in the morning, during blackout hours
        emulated_time = make_aware(datetime.combine(end, time(hour=settings.BLACKOUT_END_HOUR - 4)))
        with time_machine.travel(emulated_time, tick=False):
            tasks.end_series_subscriptions(expire_after=end)

            # Default manager filters out ended subscriptions
            self.assertTrue(models.TipSeriesSubscription._base_manager.get(pk=sub.pk).ended)
            scheduled_time = make_aware(datetime.combine(end, time(hour=settings.BLACKOUT_END_HOUR)))
            self.assertIn('eta', mocked_send_message.apply_async.call_args.kwargs)
            eta = mocked_send_message.apply_async.call_args.kwargs.get('eta')
            scheduled_time = scheduled_time.replace(minute=eta.minute, second=eta.second, microsecond=eta.microsecond)
            mocked_send_message.apply_async.assert_called_once_with((TestCase.get_test_schema_name(),
                                                                     series.end_message,
                                                                     sub.customer_id,
                                                                     OUTGOING_SMS_TYPE.SUBSCRIPTION_NOTIFICATION,
                                                                     {'subscription_id': sub.pk}),
                                                                    kwargs={'sender': settings.SMS_SENDER_AGRITIP},
                                                                    eta=scheduled_time)

    @override_settings(ENFORCE_BLACKOUT_HOURS=True)
    @patch('sms.tasks.send_message')
    def test_end_subscriptions_with_blackout_evening(self, mocked_send_message):
        start = make_aware(datetime(2017, 2, 20, 4, 0))
        end = make_aware(datetime(2017, 2, 25, 5, 0))

        series = factories.TipSeriesFactory()
        sub = factories.TipSeriesSubscriptionFactory(series=series, start=start)
        factories.TipFactory(series=series, delay=timedelta(days=5))

        # mimic an execution in the morning, during blackout hours
        emulated_time = make_aware(datetime.combine(end, time(hour=settings.BLACKOUT_BEGIN_HOUR + 4)))
        with time_machine.travel(emulated_time, tick=False):
            tasks.end_series_subscriptions(expire_after=end)

            # Default manager filters out ended subscriptions
            self.assertTrue(models.TipSeriesSubscription._base_manager.get(pk=sub.pk).ended)
            scheduled_time = end + timedelta(days=1)
            scheduled_time = make_aware(datetime.combine(scheduled_time, time(hour=settings.BLACKOUT_END_HOUR)))
            self.assertIn('eta', mocked_send_message.apply_async.call_args.kwargs)
            eta = mocked_send_message.apply_async.call_args.kwargs.get('eta')
            scheduled_time = scheduled_time.replace(minute=eta.minute, second=eta.second, microsecond=eta.microsecond)
            mocked_send_message.apply_async.assert_called_once_with((TestCase.get_test_schema_name(),
                                                                     series.end_message,
                                                                     sub.customer_id,
                                                                     OUTGOING_SMS_TYPE.SUBSCRIPTION_NOTIFICATION,
                                                                     {'subscription_id': sub.pk}),
                                                                    kwargs={'sender': settings.SMS_SENDER_AGRITIP},
                                                                    eta=scheduled_time)

    @override_settings(ENFORCE_BLACKOUT_HOURS=True)
    @patch('sms.tasks.send_message')
    def test_end_subscriptions_with_blackout_midday(self, mocked_send_message):
        start = make_aware(datetime(2017, 2, 20, 4, 0))
        end = make_aware(datetime(2017, 2, 25, 5, 0))

        series = factories.TipSeriesFactory()
        sub = factories.TipSeriesSubscriptionFactory(series=series, start=start)
        factories.TipFactory(series=series, delay=timedelta(days=5))

        # mimic an execution in the morning, during blackout hours
        emulated_time = make_aware(datetime.combine(end, time(hour=settings.BLACKOUT_END_HOUR + 4)))
        with time_machine.travel(emulated_time, tick=False):
            tasks.end_series_subscriptions(expire_after=end)

            # Default manager filters out ended subscriptions
            self.assertTrue(models.TipSeriesSubscription._base_manager.get(pk=sub.pk).ended)
            mocked_send_message.delay.assert_called_once_with(TestCase.get_test_schema_name(),
                                                              series.end_message,
                                                              sub.customer_id,
                                                              OUTGOING_SMS_TYPE.SUBSCRIPTION_NOTIFICATION,
                                                              sender=settings.SMS_SENDER_AGRITIP,
                                                              extra={'subscription_id': sub.pk},
                                                              )

    @override_settings(ENFORCE_BLACKOUT_HOURS=False)
    @patch('sms.tasks.send_message')
    def test_wait_for_all_border1_tips_without_blackout(self, mocked_send_message):
        start = make_aware(datetime(2017, 2, 20, 0, 0))
        middle = make_aware(datetime(2017, 2, 24, 1, 0))
        end = make_aware(datetime(2017, 2, 25, 1, 0))

        c1 = Border1Factory()
        c2 = Border1Factory()

        series = factories.TipSeriesFactory()
        customer = CustomerFactory(border1=c1)
        sub = factories.TipSeriesSubscriptionFactory(customer=customer, series=series, start=start)
        factories.TipFactory(series=series, delay=timedelta(days=3))
        factories.TipFactory(series=series, delay=timedelta(days=4), border1=c1)
        factories.TipFactory(series=series, delay=timedelta(days=5), border1=c2)

        tasks.end_series_subscriptions(expire_after=middle)

        sub.refresh_from_db()
        self.assertFalse(sub.ended)
        mocked_send_message.assert_not_called()

        tasks.end_series_subscriptions(expire_after=end)

        self.assertTrue(models.TipSeriesSubscription._base_manager.get(pk=sub.pk).ended)
        mocked_send_message.delay.assert_called_once_with(TestCase.get_test_schema_name(),
                                                          series.end_message,
                                                          sub.customer_id,
                                                          OUTGOING_SMS_TYPE.SUBSCRIPTION_NOTIFICATION,
                                                          sender=settings.SMS_SENDER_AGRITIP,
                                                          extra={'subscription_id': sub.pk})

    @override_settings(ENFORCE_BLACKOUT_HOURS=True)
    @patch('sms.tasks.send_message')
    def test_wait_for_all_border1_tips_with_blackout_morning(self, mocked_send_message):
        start = make_aware(datetime(2017, 2, 20, 0, 0))
        middle = make_aware(datetime(2017, 2, 24, 6, 0))
        end = make_aware(datetime(2017, 2, 25, 6, 0))

        c1 = Border1Factory()
        c2 = Border1Factory()

        series = factories.TipSeriesFactory()
        customer = CustomerFactory(border1=c1)
        sub = factories.TipSeriesSubscriptionFactory(customer=customer, series=series, start=start)
        factories.TipFactory(series=series, delay=timedelta(days=3))
        factories.TipFactory(series=series, delay=timedelta(days=4), border1=c1)
        factories.TipFactory(series=series, delay=timedelta(days=5), border1=c2)

        # mimic an execution in the morning, during blackout hours
        emulated_time = datetime.combine(middle, time(hour=settings.BLACKOUT_END_HOUR - 4))
        with time_machine.travel(emulated_time, tick=False):
            tasks.end_series_subscriptions(expire_after=middle)

            sub.refresh_from_db()
            self.assertFalse(sub.ended)
            mocked_send_message.assert_not_called()

        emulated_time = datetime.combine(end, time(hour=settings.BLACKOUT_END_HOUR - 4))
        with time_machine.travel(emulated_time, tick=False):
            tasks.end_series_subscriptions(expire_after=end)

        self.assertTrue(models.TipSeriesSubscription._base_manager.get(pk=sub.pk).ended)
        scheduled_time = make_aware(datetime.combine(end, time(hour=settings.BLACKOUT_END_HOUR)))
        self.assertIn('eta', mocked_send_message.apply_async.call_args.kwargs)
        eta = mocked_send_message.apply_async.call_args.kwargs.get('eta')
        scheduled_time = scheduled_time.replace(minute=eta.minute, second=eta.second, microsecond=eta.microsecond)
        mocked_send_message.apply_async.assert_called_once_with((TestCase.get_test_schema_name(),
                                                                 series.end_message,
                                                                 sub.customer_id,
                                                                 OUTGOING_SMS_TYPE.SUBSCRIPTION_NOTIFICATION,
                                                                 {'subscription_id': sub.pk},),
                                                                kwargs={'sender': settings.SMS_SENDER_AGRITIP},
                                                                eta=scheduled_time)

    @override_settings(ENFORCE_BLACKOUT_HOURS=True)
    @patch('sms.tasks.send_message')
    def test_wait_for_all_border1_tips_with_blackout_evening(self, mocked_send_message):
        start = make_aware(datetime(2017, 2, 20, 0, 0))
        middle = make_aware(datetime(2017, 2, 24, 4, 0))
        end = make_aware(datetime(2017, 2, 25, 4, 0))

        c1 = Border1Factory()
        c2 = Border1Factory()

        series = factories.TipSeriesFactory()
        customer = CustomerFactory(border1=c1)
        sub = factories.TipSeriesSubscriptionFactory(customer=customer, series=series, start=start)
        factories.TipFactory(series=series, delay=timedelta(days=3))
        factories.TipFactory(series=series, delay=timedelta(days=4), border1=c1)
        factories.TipFactory(series=series, delay=timedelta(days=5), border1=c2)

        # mimic an execution in the evening, during blackout hours
        emulated_time = datetime.combine(middle, time(hour=settings.BLACKOUT_BEGIN_HOUR + 2))
        with time_machine.travel(emulated_time, tick=False):
            tasks.end_series_subscriptions(expire_after=middle)

            sub.refresh_from_db()
            self.assertFalse(sub.ended)
            mocked_send_message.assert_not_called()

        emulated_time = datetime.combine(end, time(hour=settings.BLACKOUT_BEGIN_HOUR + 2))
        with time_machine.travel(emulated_time, tick=False):
            tasks.end_series_subscriptions(expire_after=end)

        self.assertTrue(models.TipSeriesSubscription._base_manager.get(pk=sub.pk).ended)
        scheduled_time = end + timedelta(hours=24 - end.hour + settings.BLACKOUT_END_HOUR)
        self.assertIn('eta', mocked_send_message.apply_async.call_args.kwargs)
        eta = mocked_send_message.apply_async.call_args.kwargs.get('eta')
        scheduled_time = scheduled_time.replace(minute=eta.minute, second=eta.second, microsecond=eta.microsecond)
        mocked_send_message.apply_async.assert_called_once_with((TestCase.get_test_schema_name(),
                                                                 series.end_message,
                                                                 sub.customer_id,
                                                                 OUTGOING_SMS_TYPE.SUBSCRIPTION_NOTIFICATION,
                                                                 {'subscription_id': sub.pk}),
                                                                kwargs={'sender': settings.SMS_SENDER_AGRITIP},
                                                                eta=scheduled_time)

    @override_settings(ENFORCE_BLACKOUT_HOURS=True)
    @patch('sms.tasks.send_message')
    def test_wait_for_all_border1_tips_with_blackout_midday(self, mocked_send_message):
        start = make_aware(datetime(2017, 2, 20, 0, 0))
        middle = make_aware(datetime(2017, 2, 24, 4, 0))
        end = make_aware(datetime(2017, 2, 25, 4, 0))

        c1 = Border1Factory()
        c2 = Border1Factory()

        series = factories.TipSeriesFactory()
        customer = CustomerFactory(border1=c1)
        sub = factories.TipSeriesSubscriptionFactory(customer=customer, series=series, start=start)
        factories.TipFactory(series=series, delay=timedelta(days=3))
        factories.TipFactory(series=series, delay=timedelta(days=4), border1=c1)
        factories.TipFactory(series=series, delay=timedelta(days=5), border1=c2)

        # mimic an execution in midday, not during blackout hours
        emulated_time = datetime.combine(middle, time(hour=settings.BLACKOUT_END_HOUR + 4))
        with time_machine.travel(emulated_time, tick=False):
            tasks.end_series_subscriptions(expire_after=middle)

            sub.refresh_from_db()
            self.assertFalse(sub.ended)
            mocked_send_message.assert_not_called()

        emulated_time = datetime.combine(end, time(hour=settings.BLACKOUT_END_HOUR + 4))
        with time_machine.travel(emulated_time, tick=False):
            tasks.end_series_subscriptions(expire_after=end)

        self.assertTrue(models.TipSeriesSubscription._base_manager.get(pk=sub.pk).ended)
        mocked_send_message.delay.assert_called_once_with(TestCase.get_test_schema_name(),
                                                          series.end_message,
                                                          sub.customer_id,
                                                          OUTGOING_SMS_TYPE.SUBSCRIPTION_NOTIFICATION,
                                                          sender=settings.SMS_SENDER_AGRITIP,
                                                          extra={'subscription_id': sub.pk},
                                                          )

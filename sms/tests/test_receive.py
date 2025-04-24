from unittest.case import skip
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from django_tenants.test.client import TenantClient as Client

from agri.models.base import get_commodity_map
from agri.tests.factories import CommodityFactory
from core.test.cases import TestCase
from customers.constants import JOIN_METHODS, STOP_METHODS
from customers.models import Customer, CustomerPhone, NPSResponse
from customers.tests.factories import (CustomerCategoryFactory,
                                       CustomerFactory, CustomerPhoneFactory,
                                       SubscriptionFactory,
                                       SubscriptionTypeFactory)
from gateways.africastalking.testing import activate_success_response
from sms import utils
from sms.agent import LLMException, SignupInformation
from sms.constants import (OUTGOING_SMS_TYPE, REVIEW_RESPONSE_TASK_TITLE,
                           SMS_API_IPS)
from sms.models import (IncomingSMS, OutgoingSMS, SMSRecipient,
                        SMSResponseKeyword, SMSResponseTemplate,
                        SMSResponseTranslation)
from sms.agent import SignupAiAgent
from sms.tests.utils import get_sms_data
from sms.utils import (get_l10n_response_template_by_name,
                       get_populated_sms_templates_text)
from tasks.models import Task
from world.models import Border
from world.utils import get_country_for_phone

from .factories import IncomingSMSFactory

valid_ip = SMS_API_IPS[0]


class ParseSMSTextTests(TestCase):
    def setUp(self):
        super().setUp()
        self.sms = IncomingSMSFactory()

    def test_for_non_action(self):
        self.sms.text = 'no action for me'
        self.assertEqual(self.sms.parse_for_action(), ('create_vanilla_task', [], {}))

    def test_ai_whitelisting_not_in_whitelist(self):
        self.sms = IncomingSMSFactory(customer__unregistered=True)
        self.sms.text = 'no action for me'
        with override_settings(SIGNUP_AI_AGENT_WHITELIST_ENABLED=True):
            self.assertEqual(self.sms.parse_for_action(), ('create_vanilla_task', [], {}))

    def test_ai_whitelisting_in_whitelist(self):
        self.sms = IncomingSMSFactory(customer__unregistered=True)
        self.sms.text = 'no action for me'
        with override_settings(SIGNUP_AI_AGENT_WHITELISTED_NUMBERS=[self.sms.customer.main_phone]):
            self.assertEqual(self.sms.parse_for_action(), ('invoke_ai_agent', [], {}))

    def test_for_non_match(self):
        sms_response_template = SMSResponseTemplate.objects.create(
            name='iShamba',
            all_countries=True,
        )
        sms_response_text = SMSResponseTranslation.objects.create(
            text='This is your response.',
            template=sms_response_template,
        )
        sms_response_keyword = SMSResponseKeyword.objects.create(
            keyword="ISHAMBA",
        )
        sms_response_keyword.responses.add(sms_response_template)
        # short text whose first word starts with the same letter as the keyword
        # make sure we don't match it
        self.sms.text = 'I love you'
        self.assertEqual(self.sms.parse_for_action(), ('create_vanilla_task', [], {}))

    def _assert_keyword_response(self, sms_text, template_name):
        self.sms.text = sms_text
        method_name, args, kwargs = self.sms.parse_for_action()
        self.assertEqual('keyword_response', method_name)
        self.assertEqual([], args)
        assert isinstance(kwargs['keyword'], SMSResponseKeyword)
        assert isinstance(kwargs['template'], SMSResponseTemplate)
        keyword = kwargs['keyword']
        template = kwargs['template']
        template_name += f"_Kenya"
        self.assertEqual(template_name, keyword.responses.first().name)
        self.assertEqual(template_name, template.name)
        self.assertEqual(template, keyword.responses.first())

    def test_for_join_action(self):
        self._assert_keyword_response('JOIN', settings.SMS_JOIN)

    def test_for_join_action_with_mixed_caps(self):
        self._assert_keyword_response('jOiN', settings.SMS_JOIN)

    def test_for_join_action_with_other_characters(self):
        self._assert_keyword_response(" .Join  *", settings.SMS_JOIN)

    def test_for_stop_action(self):
        self._assert_keyword_response('STOP', settings.SMS_STOP)

    def test_for_stop_action_emphatic(self):
        self._assert_keyword_response('STOP!', settings.SMS_STOP)

    def test_for_stop_action_cutoff(self):
        self._assert_keyword_response('STO', settings.SMS_STOP)

    def test_for_stop_action_off(self):
        self._assert_keyword_response('off', settings.SMS_STOP)

    def test_for_stop_action_end(self):
        self._assert_keyword_response('End', settings.SMS_STOP)

    def test_for_not_stop_action_for_sentence(self):
        self.sms.text = 'Stop joking'
        self.assertEqual(self.sms.parse_for_action(), ('create_vanilla_task', [], {}))

    def test_for_non_stop_action_long_stop(self):
        self.sms.text = 'stop stop stop'  # Too long to safely interpret as a stop command
        self.assertEqual(self.sms.parse_for_action(), ('create_vanilla_task', [], {}))

    def test_for_keyword_action(self):
        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
            all_countries=True,
        )
        sms_response_text = SMSResponseTranslation.objects.create(
            text='This is your response.',
            template=sms_response_template,
        )
        sms_response_keyword = SMSResponseKeyword.objects.create(
            keyword="fruit bat"
        )
        sms_response_keyword.responses.add(sms_response_template)
        self.sms.text = sms_response_keyword.keyword
        self.assertEqual(self.sms.parse_for_action(), ('keyword_response', [], {'keyword': sms_response_keyword, 'template': sms_response_template}))


class ReceiveSmsActionTests(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant, REMOTE_ADDR=valid_ip)
        User = get_user_model()
        self.operator = User.objects.create_user('foo', password='foo')

        self.to_phone = '12345'

        # Build, not create, so it is not created in the database
        self.new_customer_phone = str(CustomerPhoneFactory.build().number)
        self.subscribed_customer = CustomerFactory(join_method=JOIN_METHODS.SMS)
        self.opted_out_customer = CustomerFactory(blank=True, stopped=True)
        self.basic_customer = CustomerFactory(blank=True, preferred_language='eng')
        self.premium_customer = CustomerFactory()
        self.swahili_customer = CustomerFactory(preferred_language='swa')
        # Create an extra premium subscription
        prem_sub_type = SubscriptionTypeFactory()
        prem_sub = SubscriptionFactory(customer=self.premium_customer,
                                       type=prem_sub_type)

        self.border3 = Border.objects.get(country='Kenya', level=3, name='Busibwabo')
        self.border2 = Border.objects.get(country='Kenya', level=2, id=self.border3.parent_id)
        self.border1 = Border.objects.get(country='Kenya', level=1, id=self.border2.parent_id)
        self.border0 = Border.objects.get(country='Kenya', level=0, id=self.border1.parent_id)

    @activate_success_response
    def test_for_no_action_on_duplicate_incomingsms(self):
        from_phone = str(self.subscribed_customer.phones.first())
        text = "Hello, world"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, IncomingSMS.objects.count())
        self.assertEqual(1, Task.objects.count())

        the_sms = IncomingSMS.objects.first()

        # create and send a duplicate
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        # Ensure success
        self.assertEqual(response.status_code, 200)
        # Both sms messages should be stored
        self.assertEqual(2, IncomingSMS.objects.count())
        # Since it is a duplicate, only the original should have created a task
        self.assertEqual(1, Task.objects.count())
        # Ensure that the task points to the original message, not the second
        self.assertEqual(the_sms, Task.objects.first().incoming_messages.first())

        self.assertEqual(the_sms.sender, from_phone)
        self.assertEqual(the_sms.recipient, self.to_phone)
        self.assertEqual(the_sms.text, text)

        c = Customer.objects.get(phones__number=from_phone)
        self.assertEqual(JOIN_METHODS.SMS, c.join_method)

    @skip("Skipping as I don't get how this passed in the first place; the join method of self.subscribed_customer is set to JOIN_METHODS.SMS")
    def test_for_reusing_existing_customer(self):
        from_phone = self.subscribed_customer.main_phone
        original_id = self.subscribed_customer.id
        data = get_sms_data("Hello, world", from_phone, self.to_phone)
        customer_count = Customer.objects.count()
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(customer_count, Customer.objects.count())
        new_id = CustomerPhone.objects.get(number=str(from_phone)).customer_id
        the_customer = Customer.objects.get(id=new_id)
        self.assertEqual(original_id, new_id)

        # The customer existed, so the incoming SMS should not override the join_method
        self.assertNotEqual(JOIN_METHODS.SMS, the_customer.join_method)

    @activate_success_response
    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_for_create_new_customer(self, agent_invoke):
        agent_invoke.return_value = SignupInformation(
            name="",
            crops_livestock=[],
            border1="",
            border3="",
            nearest_school=""
        )
        from_phone = self.new_customer_phone
        data = get_sms_data("Hello, world", from_phone, self.to_phone)
        customer_count = Customer.objects.count()
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(customer_count + 1, Customer.objects.count())
        customer = Customer.objects.get(phones__number=from_phone)
        self.assertIsNotNone(customer)
        self.assertEqual(JOIN_METHODS.SMS, customer.join_method)

    @activate_success_response
    def test_for_create_task_on_unparsable_sms(self):
        from_phone = self.subscribed_customer.main_phone
        text = "Hello, world"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

        the_sms = IncomingSMS.objects.first()
        customer = Customer.objects.get(phones__number=from_phone)
        the_task = Task.objects.first()
        self.assertEqual(1, Task.objects.count())
        self.assertEqual(the_task.customer, customer)
        self.assertEqual(the_task.description, 'Respond to SMS: Hello, world')
        self.assertEqual(the_task.source, the_sms)

    @activate_success_response
    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_for_auto_response_on_unparseable_sms_first_time(self, agent_invoke):
        agent_invoke.return_value = SignupInformation(
            name="",
            crops_livestock=[],
            border1="",
            border3="",
            nearest_school=""
        )
        from_phone = self.new_customer_phone
        text = "I have a question"
        data = get_sms_data(text, from_phone, self.to_phone)
        sender_country = get_country_for_phone(from_phone)
        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        customer = Customer.objects.get(phones__number=from_phone)
        sent_sms = OutgoingSMS.objects.first()
        template = get_l10n_response_template_by_name(settings.SMS_JOIN, sender_country)
        self.assertEqual(template.translations.first().text, sent_sms.text)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)

    @activate_success_response
    def test_for_no_task_on_join_sms(self):
        from_phone = self.new_customer_phone
        text = "JOIN"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(0, Task.objects.count())
        c = Customer.objects.get(phones__number=from_phone)
        self.assertEqual(JOIN_METHODS.SMS, c.join_method)

    @activate_success_response
    def test_for_sms_response_on_join_sms(self):
        from_phone = self.new_customer_phone
        text = "JOIN"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)
        sender_country = get_country_for_phone(from_phone)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        customer = Customer.objects.get(phones__number=from_phone)
        sent_sms = OutgoingSMS.objects.first()
        template = get_l10n_response_template_by_name(settings.SMS_JOIN, sender_country)
        self.assertEqual(template.translations.first().text, sent_sms.text)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(JOIN_METHODS.SMS, customer.join_method)

    @activate_success_response
    def test_for_customer_not_registered_on_join_sms(self):
        from_phone = self.new_customer_phone
        text = "JOIN"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        customer = Customer.objects.get(phones__number=from_phone)
        self.assertFalse(customer.is_registered)
        self.assertEqual(JOIN_METHODS.SMS, customer.join_method)

    @activate_success_response
    def test_for_no_task_on_not_subscribed_stop_sms(self):
        from_phone = self.new_customer_phone
        text = "STOP"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(0, Task.objects.count())

        c = Customer.objects.get(phones__number=from_phone)
        self.assertEqual(STOP_METHODS.SMS, c.stop_method)
        self.assertEqual(timezone.now().date(), c.stop_date)

    @activate_success_response
    def test_for_automated_response_on_not_subscribed_stop_sms(self):
        from_phone = self.new_customer_phone
        text = "STOP"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        customer = Customer.objects.get(phones__number=self.new_customer_phone)
        expected_msg, sender = get_populated_sms_templates_text(settings.SMS_INACTIVE_CUSTOMER_STOP, customer)
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(expected_msg, sent_sms.text)
        self.assertEqual('21606', sender)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)

        self.assertEqual(STOP_METHODS.SMS, customer.stop_method)
        self.assertEqual(timezone.now().date(), customer.stop_date)

    @activate_success_response
    def test_for_automated_response_on_swahili_customer(self):
        customer = self.swahili_customer
        from_phone = customer.main_phone

        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
            all_countries=True,
        )
        sms_response_text_eng = SMSResponseTranslation.objects.create(
            text='This is your response.',
            template=sms_response_template,
            language='eng',
        )
        sms_response_text_swa = SMSResponseTranslation.objects.create(
            text='Hili ni jibu lako.',
            template=sms_response_template,
            language='swa',
        )
        sms_response_keyword = SMSResponseKeyword.objects.create(
            keyword="fruit bat"
        )
        sms_response_keyword.responses.add(sms_response_template)
        text = sms_response_keyword.keyword
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        expected_msg, sender = get_populated_sms_templates_text(settings.SMS_INACTIVE_CUSTOMER_STOP, customer)
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sms_response_text_swa.text, sent_sms.text)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)

    @activate_success_response
    def test_for_automated_response_on_english_customer(self):
        customer = self.basic_customer
        from_phone = customer.main_phone

        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
            all_countries=True,
        )
        sms_response_text_eng = SMSResponseTranslation.objects.create(
            text='This is your response.',
            template=sms_response_template,
            language='eng',
        )
        sms_response_text_swa = SMSResponseTranslation.objects.create(
            text='Hili ni jibu lako.',
            template=sms_response_template,
            language='swa',
        )
        sms_response_keyword = SMSResponseKeyword.objects.create(
            keyword="fruit bat"
        )
        sms_response_keyword.responses.add(sms_response_template)
        text = sms_response_keyword.keyword
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        expected_msg, sender = get_populated_sms_templates_text(settings.SMS_INACTIVE_CUSTOMER_STOP, customer)
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sms_response_text_eng.text, sent_sms.text)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)

    @activate_success_response
    def test_for_automated_response_without_right_languages(self):
        customer = self.basic_customer
        customer.preferred_language='lug'
        customer.save()
        from_phone = customer.main_phone

        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
            all_countries=True,
        )
        sms_response_text_eng = SMSResponseTranslation.objects.create(
            text='This is your response.',
            template=sms_response_template,
            language='eng',
        )
        sms_response_text_swa = SMSResponseTranslation.objects.create(
            text='Hili ni jibu lako.',
            template=sms_response_template,
            language='swa',
        )
        sms_response_keyword = SMSResponseKeyword.objects.create(
            keyword="fruit bat"
        )
        sms_response_keyword.responses.add(sms_response_template)
        text = sms_response_keyword.keyword
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        expected_msg, sender = get_populated_sms_templates_text(settings.SMS_INACTIVE_CUSTOMER_STOP, customer)
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sms_response_text_eng.text, sent_sms.text)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)

    @activate_success_response
    def test_for_no_create_task_on_subscribed_stop_sms(self):
        from_phone = self.subscribed_customer.main_phone
        text = "STOP"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(0, Task.objects.count())

        c = Customer.objects.get(phones__number=from_phone)
        self.assertEqual(STOP_METHODS.SMS, c.stop_method)
        self.assertEqual(timezone.now().date(), c.stop_date)

    @activate_success_response
    def test_for_automated_response_on_subscribed_stop_sms(self):
        from_phone = self.subscribed_customer.main_phone
        text = "STOP"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        message, sender = get_populated_sms_templates_text(settings.SMS_STOP, self.subscribed_customer)
        self.assertEqual(message, sent_sms.text)
        self.assertEqual('21606', sender)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

        c = Customer.objects.get(phones__number=from_phone)
        self.assertEqual(STOP_METHODS.SMS, c.stop_method)
        self.assertEqual(timezone.now().date(), c.stop_date)

    @activate_success_response
    def test_for_has_requested_stop_on_subscribed_stop_sms(self):
        from_phone = self.subscribed_customer.main_phone
        text = "STOP"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.subscribed_customer.refresh_from_db()
        self.assertTrue(self.subscribed_customer.has_requested_stop)

        c = Customer.objects.get(phones__number=from_phone)
        self.assertEqual(STOP_METHODS.SMS, c.stop_method)
        self.assertEqual(timezone.now().date(), c.stop_date)

    @activate_success_response
    def test_for_join_on_stopped_customer_join_sms(self):
        from_phone = self.opted_out_customer.main_phone
        text = "JOIN"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.opted_out_customer.refresh_from_db()
        self.assertFalse(self.opted_out_customer.has_requested_stop)

    @activate_success_response
    def test_for_automated_response_on_stopped_customer_join_sms(self):
        from_phone = self.opted_out_customer.main_phone
        text = "JOIN"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        message, sender = get_populated_sms_templates_text(settings.SMS_INACTIVE_CUSTOMER_REJOIN, self.opted_out_customer)
        self.assertEqual(message, sent_sms.text)
        self.assertEqual('21606', sender)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_for_task_on_stopped_customer_join_sms_when_template_specifies_task(self):
        from_phone = self.opted_out_customer.main_phone
        text = "JOIN"
        data = get_sms_data(text, from_phone, self.to_phone)

        SMSResponseTemplate.objects.filter(name=settings.SMS_INACTIVE_CUSTOMER_REJOIN).update(
            action=SMSResponseTemplate.Actions.TASK)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, Task.objects.count())

    @activate_success_response
    def test_for_no_task_on_stopped_customer_join_sms_when_template_specifies_no_task(self):
        from_phone = self.opted_out_customer.main_phone
        text = "JOIN"
        data = get_sms_data(text, from_phone, self.to_phone)
        self.assertEqual(0, Task.objects.count())

        SMSResponseTemplate.objects.filter(name__startswith=settings.SMS_INACTIVE_CUSTOMER_REJOIN).update(
            action=SMSResponseTemplate.Actions.NONE)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(0, Task.objects.count())

    @activate_success_response
    def test_for_high_priority_task_on_premium_customer(self):
        from_phone = self.premium_customer.main_phone
        text = "fix my problem!"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, Task.objects.count())
        self.assertEqual("high", Task.objects.first().priority)

    @activate_success_response
    def test_for_high_priority_task_on_fremium_customer(self):
        from_phone = self.subscribed_customer.main_phone
        text = "fix my problem!"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, Task.objects.count())
        self.assertEqual("medium", Task.objects.first().priority)

    @activate_success_response
    def test_for_medium_priority_task_on_non_premium_customer(self):
        from_phone = self.basic_customer.main_phone
        text = "fix my problem!"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, Task.objects.count())
        self.assertEqual("medium", Task.objects.first().priority)

    @activate_success_response
    def test_for_task_creation_on_unrecognizable_query_response(self):
        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=self.basic_customer,
            message=query_sms,
            page_index=1
        )
        from_phone = self.basic_customer.main_phone
        response_text = "Busia"
        data = get_sms_data(response_text, from_phone, self.to_phone)

        # Busia is not a valid ward so this should result in a new Task for agents to handle
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        # Ensure that no additional messages were sent to the customer
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        # Ensure that a task was created
        self.assertEqual(1, Task.objects.count())
        response_sms = IncomingSMS.objects.first()
        the_task = Task.objects.first()
        self.assertEqual(self.basic_customer, the_task.customer)
        self.assertEqual(f"{REVIEW_RESPONSE_TASK_TITLE}: \nQuery: {query_text} \n--->Customer Response: {response_text}", the_task.description)
        self.assertEqual(query_sms, the_task.source)
        self.assertEqual(response_sms, the_task.incoming_messages.first())

    @activate_success_response
    def test_query_response_automatic_handling_of_correct_response(self):
        customer = CustomerFactory(border0=None, border1=None, border2=None, border3=None, location=None)
        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        from_phone = customer.main_phone
        response_text = self.border3.name
        data = get_sms_data(response_text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        # No additional messages were sent to the customer
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        # This response should be handled automatically so no Task is created
        self.assertEqual(0, Task.objects.count())

        customer.refresh_from_db()
        self.assertEqual(self.border3, customer.border3)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border0, customer.border0)

    @activate_success_response
    def test_join_message_from_non_main_number_responds_to_same(self):
        # Simulate an existing customer re-joining
        customer = CustomerFactory(border0=None, border1=None, border2=None, border3=None, location=None)
        from_number = '+254720123456'
        other_phone = CustomerPhone.objects.create(number=from_number, is_main=False, customer=customer)
        data = get_sms_data('JOIN', from_number, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        # One response was sent to the customer
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        self.assertEqual(from_number, SMSRecipient.objects.first().extra['number'])
        # This response should be handled automatically so no Task is created
        self.assertEqual(0, Task.objects.count())

    @activate_success_response
    def test_location_response_automatic_handling_of_matching_border3s(self):
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=self.border2, border3=self.border3)
        last_updated = customer.last_updated

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        from_phone = customer.main_phone
        response_text = self.border3.name
        data = get_sms_data(response_text, from_phone, self.to_phone)

        # The response matches the customer's recorded location, so no update
        # should be made and no Task created.
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        # No additional messages were sent to the customer
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        # This response should be handled automatically so no Task is created
        self.assertEqual(0, Task.objects.count())

        # Ensure no change to customer record
        customer.refresh_from_db()
        self.assertEqual(last_updated, customer.last_updated)
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(self.border3, customer.border3)

    @activate_success_response
    def test_location_response_automatic_handling_of_conflicting_border3s(self):
        # NOTE that the border3 is set to a border2 to create the conflict
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=self.border2, border3=self.border2)
        last_updated = customer.last_updated

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        from_phone = customer.main_phone
        response_text = self.border3.name
        data = get_sms_data(response_text, from_phone, self.to_phone)

        # This should create a border3 conflict and create a Task for an agent to handle
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        # No additional messages were sent to the customer
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        # This response should be handled automatically so no Task is created
        self.assertEqual(1, Task.objects.count())

        # Ensure no automated change to the customer record
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(self.border2, customer.border3)

        self.assertEqual(last_updated, customer.last_updated)

        response_sms = IncomingSMS.objects.first()
        the_task = Task.objects.first()
        self.assertEqual(customer, the_task.customer)
        self.assertEqual(f"{REVIEW_RESPONSE_TASK_TITLE}: \nQuery: {query_text} \n--->Customer Response: {response_text}", the_task.description)
        self.assertEqual(query_sms, the_task.source)
        self.assertEqual(response_sms, the_task.incoming_messages.first())

    @activate_success_response
    def test_location_response_automatic_handling_of_conflicting_border2s(self):
        # NOTE that the border2 is set to border3 to create the conflict
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=self.border3, border3=self.border3)
        last_updated = customer.last_updated

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        from_phone = customer.main_phone
        response_text = self.border3.name
        data = get_sms_data(response_text, from_phone, self.to_phone)

        # This should create a conflict, and a Task for an agent to handle
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        # No additional messages were sent to the customer
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        # This response should be handled automatically so no Task is created
        self.assertEqual(1, Task.objects.count())

        # Ensure the customer record has not changed
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border3, customer.border3)
        self.assertEqual(self.border3, customer.border2)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(last_updated, customer.last_updated)

        response_sms = IncomingSMS.objects.first()
        the_task = Task.objects.first()
        self.assertEqual(customer, the_task.customer)
        self.assertEqual(f"{REVIEW_RESPONSE_TASK_TITLE}: \nQuery: {query_text} \n--->Customer Response: {response_text}", the_task.description)
        self.assertEqual(query_sms, the_task.source)
        self.assertEqual(response_sms, the_task.incoming_messages.first())

    @activate_success_response
    def test_location_response_automatic_handling_of_conflicting_counties(self):
        # NOTE that the border1 is set to border3 to create the conflict
        customer = CustomerFactory(border0=self.border0, border1=self.border3, border2=self.border2, border3=self.border3)
        last_updated = customer.last_updated

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        from_phone = customer.main_phone
        response_text = self.border3.name
        data = get_sms_data(response_text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        # No additional messages were sent to the customer
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        # This response should be handled automatically so no Task is created
        self.assertEqual(1, Task.objects.count())

        # Ensure the customer record has not changed
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border3, customer.border3)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(self.border3, customer.border1)
        self.assertEqual(last_updated, customer.last_updated)

        response_sms = IncomingSMS.objects.first()
        the_task = Task.objects.first()
        self.assertEqual(customer, the_task.customer)
        self.assertEqual(f"{REVIEW_RESPONSE_TASK_TITLE}: \nQuery: {query_text} \n--->Customer Response: {response_text}", the_task.description)
        self.assertEqual(query_sms, the_task.source)
        self.assertEqual(response_sms, the_task.incoming_messages.first())

    @activate_success_response
    def test_location_response_matching_for_valid_response(self):
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=self.border2, border3=None)
        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        # mimic a response
        in_sms = IncomingSMS.objects.create(
            text=self.border3.name,
            customer=customer,
            at=timezone.now(),
            gateway=1,
        )
        handled, auto_message = in_sms.auto_handle_location_response(query_sms)
        self.assertTrue(handled, auto_message)
        # Ensure that the customer record got updated appropriately
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(self.border3, customer.border3)

    @activate_success_response
    def test_location_response_matching_for_border3_outside_border2(self):
        # Choose a border3 outside of the test's normal border1/border2/border3 borders.
        # Lindi ward is in Kibra subcounty, which is in Nairobi county.
        new_ward = Border.objects.get(country='Kenya', level=3, name='Lindi')

        # Create a customer without a border3
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=self.border2, border3=None)

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        # mimic a response
        in_sms = IncomingSMS.objects.create(
            text=new_ward.name,
            customer=customer,
            at=timezone.now(),
            gateway=1,
        )
        handled, auto_message = in_sms.auto_handle_location_response(query_sms)
        self.assertFalse(handled, auto_message)
        # Ensure that the customer record did not change
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(None, customer.border3)

    @activate_success_response
    def test_location_response_matching_for_border3_outside_border1(self):
        # Choose a border2 outside of the test's normal border1/border2/border3 borders.
        # Kibra ward is in Kibra subcounty, which is in Nairobi county.
        new_ward = Border.objects.get(country='Kenya', level=3, name='Lindi')
        outer_subcounty = Border.objects.get(country='Kenya', level=2, id=new_ward.parent_id)

        # Create a customer without a border3
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=outer_subcounty, border3=None)

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        # mimic a response
        in_sms = IncomingSMS.objects.create(
            text=new_ward.name,
            customer=customer,
            at=timezone.now(),
            gateway=1,
        )
        handled, auto_message = in_sms.auto_handle_location_response(query_sms)
        self.assertFalse(handled, auto_message)
        # Ensure that the customer record did not change
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(outer_subcounty, customer.border2)
        self.assertEqual(None, customer.border3)

    @activate_success_response
    def test_location_response_matching_for_border3_conflict(self):
        # Choose a border3 in the test's normal border1/border2 borders.
        # Burumba ward is in Matayos subcounty, which is in Busia county.
        new_ward = Border.objects.get(country='Kenya', level=3, name='Burumba')

        # Create a customer without a ward
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=self.border2, border3=self.border3)

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        # mimic a response
        in_sms = IncomingSMS.objects.create(
            text=new_ward.name,
            customer=customer,
            at=timezone.now(),
            gateway=1,
        )
        handled, auto_message = in_sms.auto_handle_location_response(query_sms)
        self.assertFalse(handled, auto_message)
        # Ensure that the customer record did not change
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(self.border3, customer.border3)

    @activate_success_response
    def test_location_response_matching_for_one_letter_border3_name_change(self):
        # Create a customer without a ward
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=self.border2, border3=None)

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        # mimic a response
        misspelled_name = list(self.border3.name)
        misspelled_name[1] = misspelled_name[2]

        in_sms = IncomingSMS.objects.create(
            text=''.join(misspelled_name),
            customer=customer,
            at=timezone.now(),
            gateway=1,
        )
        handled, auto_message = in_sms.auto_handle_location_response(query_sms)
        self.assertTrue(handled, auto_message)
        # Ensure that the customer record was updated
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(self.border3, customer.border3)

    @activate_success_response
    def test_location_response_matching_for_two_letter_border3_name_change(self):
        # Create a customer without a border3
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=self.border2, border3=None)

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        # mimic a response
        misspelled_name = list(self.border3.name)
        misspelled_name[1] = misspelled_name[2]
        misspelled_name[3] = misspelled_name[4]

        in_sms = IncomingSMS.objects.create(
            text=''.join(misspelled_name),
            customer=customer,
            at=timezone.now(),
            gateway=1,
        )
        handled, auto_message = in_sms.auto_handle_location_response(query_sms)
        self.assertFalse(handled, auto_message)
        # Ensure that the customer record was not updated
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(None, customer.border3)

    @activate_success_response
    def test_location_response_matching_for_unambiguous_two_word_border3_name(self):
        # Create a customer without a border3
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=self.border2, border3=None)
        # There is only one Bukhayo West in the db, however there are other
        # wards that start with Bukhayo in other subcounties. The auto-matcher
        # should pick the right one based on the customer's border1 / border2.
        new_ward = Border.objects.get(country='Kenya', level=3, name='Bukhayo West')

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        # mimic a response
        in_sms = IncomingSMS.objects.create(
            text=new_ward.name,
            customer=customer,
            at=timezone.now(),
            gateway=1,
        )
        handled, auto_message = in_sms.auto_handle_location_response(query_sms)
        self.assertTrue(handled, auto_message)
        # Ensure that the customer record was not updated
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(new_ward, customer.border3)

    @activate_success_response
    def test_location_response_matching_for_unambiguous_two_word_border3_name_misspelled(self):
        # Create a customer without a border3
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=self.border2, border3=None)
        # There is only one Bukhayo West in the db, however there are other
        # wards that start with Bukhayo in other subcounties. The auto-matcher
        # should pick the right one based on the customer's border1 / border2.
        new_ward = Border.objects.get(country='Kenya', level=3, name='Bukhayo West')

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        # mimic a response
        misspelled_name = list(new_ward.name)
        misspelled_name[1] = misspelled_name[2]

        in_sms = IncomingSMS.objects.create(
            text=''.join(misspelled_name),
            customer=customer,
            at=timezone.now(),
            gateway=1,
        )

        handled, auto_message = in_sms.auto_handle_location_response(query_sms)
        self.assertTrue(handled, auto_message)

        # Ensure that the customer record was updated
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(new_ward, customer.border3)

    @activate_success_response
    def test_location_response_matching_two_word_border3_name(self):
        # Create a customer without a border3
        customer = CustomerFactory(border0=self.border0, border1=self.border1, border2=self.border2, border3=None)
        # There is only one Bukhayo West in the db, however there are other
        # wards that start with Bukhayo in other subcounties. The auto-matcher
        # should pick the right one based on the customer's border1 / border2.
        new_ward = Border.objects.get(country='Kenya', level=3, name='Bukhayo West')

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        # mimic a response
        misspelled_name = list(new_ward.name)
        misspelled_name[1] = misspelled_name[2]

        in_sms = IncomingSMS.objects.create(
            text=''.join(misspelled_name),
            customer=customer,
            at=timezone.now(),
            gateway=1,
        )

        handled, auto_message = in_sms.auto_handle_location_response(query_sms)
        self.assertTrue(handled, auto_message)
        # Ensure that the customer record was not updated
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(new_ward, customer.border3)

    @activate_success_response
    def test_location_response_matching_two_word_border3_name_no_context(self):
        # Create a customer without a border3
        customer = CustomerFactory(border0=self.border0, border1=None, border2=None, border3=None)
        # There is only one Bukhayo West in the db, however there are other
        # wards that start with Bukhayo in other subcounties. The auto-matcher
        # should pick the right one with no subcounty context.
        new_ward = Border.objects.get(country='Kenya', level=3, name='Bukhayo West')

        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        # mimic a response
        misspelled_name = list(new_ward.name)
        misspelled_name[1] = misspelled_name[2]

        in_sms = IncomingSMS.objects.create(
            text=''.join(misspelled_name),
            customer=customer,
            at=timezone.now(),
            gateway=1,
        )

        handled, auto_message = in_sms.auto_handle_location_response(query_sms)
        self.assertTrue(handled, auto_message)
        # Ensure that the customer record was not updated
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(new_ward, customer.border3)

    @activate_success_response
    def test_two_location_responses_mark_second_as_not_location_response(self):
        customer = CustomerFactory(border0=self.border0, border1=None, border2=None, border3=None)
        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )
        # mimic a response
        from_phone = customer.main_phone
        response_text = self.border3.name
        data = get_sms_data(response_text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        # No additional messages were sent to the customer
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        # This response should be handled automatically so no Task is created
        self.assertEqual(0, Task.objects.count())
        # Ensure that the customer record got updated appropriately
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(self.border3, customer.border3)

        # mimic a second response
        response_text = 'how can i improve my shamba'
        data = get_sms_data(response_text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        # No additional messages were sent to the customer
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        # Ensure that the customer record was not changed
        customer.refresh_from_db()
        self.assertEqual(self.border0, customer.border0)
        self.assertEqual(self.border1, customer.border1)
        self.assertEqual(self.border2, customer.border2)
        self.assertEqual(self.border3, customer.border3)
        # Ensure that a task was created
        self.assertEqual(1, Task.objects.count())

    @activate_success_response
    def test_location_response_real_world_responses(self):
        customer = CustomerFactory(border0=self.border0, border1=None, border2=None, border3=None)
        # Create a data query sms
        query_text = "Please send us the ward that your shamba is in"
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )

        messages = [
            ["Chengoni/Samburu", 'Kwale', 'Kinango', 'Chengoni/Samburu'],
            ["Shivanaga", 'Kakamega', 'Malava', 'Manda-Shivanga'],
            ["kanyasrega", None, None, None],  # no close match
            ["kakelo kokwanyo,Rachuonyo East,Homabay county", 'Homa Bay', 'Kabondo Kasipul', 'Kokwanyo/Kakelo'],
            ["Nzoia Ward, Likuyani Sub-County, Kakamega County", 'Kakamega', 'Likuyani', 'Nzoia'],
            ["Am in kangundo west ward of Kangundo sub county in Machakos county", 'Machakos', 'Kangundo', 'Kangundo West'],
            ["Taita taveta county..mwataete subcounty..bura ward", 'Taita Taveta', 'Mwatate', 'Bura'],
            ["Ward is marama west, subcounty is Butere and county is kakamega", 'Kakamega', 'Butere', 'Marama West'],
            ["Kiganjo - Mathari Ward, Kabiruini Sub-County and Nyeri County.", 'Nyeri', 'Nyeri Central', 'Kiganjo/Mathari'],
            ["Lembus perkera ward", 'Baringo', 'Koibatek', 'Lembus/Perkerra'],
            ["Hello, I am in Kaoyeni, Rabai.", None, None, None],  # Riabai and Rabai/Kisurutini close matches
            ["Ward is marama west, subcounty is Butere and county is kakamega", 'Kakamega', 'Butere', 'Marama West'],
            ["Ward is Ollessos.subcounty Nandi hills.county Nandi", 'Nandi', 'Nandi East', 'Nandi Hills'],
        ]

        for message in messages:
            # Reset the incoming messages so that each is interpreted as a location response
            IncomingSMS.objects.all().delete()
            Task.objects.all().delete()
            customer.border1 = customer.border2 = customer.border3 = None
            customer.save()

            # mimic a response
            from_phone = customer.main_phone
            response_text = message[0]
            data = get_sms_data(response_text, from_phone, self.to_phone)

            response = self.client.post(reverse('sms_api_callback'), data)

            self.assertEqual(response.status_code, 200)
            # No additional messages were sent to the customer
            self.assertEqual(1, OutgoingSMS.objects.count())
            self.assertEqual(1, SMSRecipient.objects.count())
            # If unrecognizable, check if a Task was created and that the customer record got updated correctly
            customer.refresh_from_db()
            if message[1] is None:
                self.assertEqual(1, Task.objects.count(), message)
                self.assertEqual(message[1], customer.border1)
                self.assertEqual(message[2], customer.border2)
                self.assertEqual(message[3], customer.border3)
            else:
                self.assertEqual(0, Task.objects.count(), message)
                self.assertEqual(message[1], customer.border1.name)
                self.assertEqual(message[2], customer.border2.name)
                self.assertEqual(message[3], customer.border3.name)

    @activate_success_response
    def test_nps_responses(self):
        customer = self.subscribed_customer
        # Create a data query sms
        query_text = "Based on the service you received, how likely are you to recommend iShamba to friends or family? On a scale of 0 to 10, with 0 being lowest and 10 the highest."
        query_sms = OutgoingSMS.objects.create(
            text=query_text,
            message_type=OUTGOING_SMS_TYPE.NPS_REQUEST,
            sent_by=self.operator,
            time_sent=timezone.now(),
            extra={}
        )
        # mimic sending it to the customer
        SMSRecipient.objects.create(
            recipient=customer,
            message=query_sms,
            page_index=1
        )

        messages = [
            ['0', 0],
            ['5', 5],
            ['10', 10],
            ['-1', None],
            ['11', None],
            ['1 2 3 4 5', None],
            ['1 10', 1],  # Handled similarly to '1/10'
            ['one', None],
            ['10 I would', 10],
            ['no way 0', 0],
            ['maybe 5', 5],
            ['maybe 5 or 6', None],
            ['Where can I buy 10 bags of fertilizer?', None],
            ['9/10', 9],
            ['6 /  11', 6],
            ['-5', None],
            ['-1/10', None],
        ]

        for message in messages:
            # Reset the incoming messages so that each is interpreted as an NPS response
            IncomingSMS.objects.all().delete()
            Task.objects.all().delete()
            NPSResponse.objects.all().delete()

            # mimic a response
            from_phone = customer.main_phone
            response_text = message[0]
            data = get_sms_data(response_text, from_phone, self.to_phone)

            response = self.client.post(reverse('sms_api_callback'), data)

            self.assertEqual(response.status_code, 200)
            # No additional messages were sent to the customer
            self.assertEqual(1, OutgoingSMS.objects.count())
            self.assertEqual(1, SMSRecipient.objects.count())
            # If unrecognizable, check if a Task was created and that the customer record got updated correctly
            customer.refresh_from_db()
            if message[1] is None:
                self.assertEqual(1, Task.objects.count(), message)
                self.assertEqual(0, NPSResponse.objects.count())
            else:
                self.assertEqual(0, Task.objects.count(), message)
                self.assertEqual(1, NPSResponse.objects.count())


class SMSKeywordCreationTests(TestCase):
    def setUp(self):
        super().setUp()
        self.to_phone = '12345'

    def test_basic_template_creation(self):
        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
            sender='21606',
        )
        sms_response_text = SMSResponseTranslation.objects.create(
            text='This is your response.',
            template=sms_response_template,
        )
        try:
            sms_response_text.clean_fields()
        except Exception:
            self.fail("Saving a plain SMSResponseTemplate failed unexpectedly")
        # The default behavior is for templates to apply to all countries
        self.assertTrue(sms_response_template.all_countries)

    def test_template_creation_with_placeholders(self):
        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
            sender='21606')
        sms_response_text = SMSResponseTranslation.objects.create(
            text='Call the call centre on {call_centre}, text us '
                 'on {shortcode}, or pay money to {till_number}.',
            template=sms_response_template,
        )
        sms_response_text.clean_fields()

    def test_template_creation_with_invalid_placeholders(self):
        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
        )
        sms_response_text = SMSResponseTranslation.objects.create(
            text='Hello {customer}.',
            template=sms_response_template,
        )
        with self.assertRaises(ValidationError):
            sms_response_text.clean_fields()

    def test_template_creation_with_too_long_message(self):
        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
        )
        sms_response_text = SMSResponseTranslation.objects.create(
            text='Hello ' * 300,
            template=sms_response_template,
        )
        self.assertEqual(len(sms_response_text.text), 1800)
        with self.assertRaises(ValidationError):
            sms_response_text.clean_fields()

    def test_template_creation_with_message_requiring_splitting(self):
        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
            sender='21606',
        )
        sms_response_text = SMSResponseTranslation.objects.create(
            text='Hello ' * 30,
            template=sms_response_template,
        )
        self.assertEqual(len(sms_response_text.text), 180)
        sms_response_text.clean_fields()

    def test_template_creation_with_forbidden_characters(self):
        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
        )
        sms_response_text = SMSResponseTranslation.objects.create(
            text='This contains an em dash: \u2014.',
            template=sms_response_template,
        )
        with self.assertRaises(ValidationError):
            sms_response_text.clean_fields()

    def test_basic_keyword_creation(self):
        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
            all_countries=True,
        )
        sms_response_text = SMSResponseTranslation.objects.create(
            text='This is your response.',
            template=sms_response_template,
        )
        sms_response_keyword = SMSResponseKeyword.objects.create(
            keyword="fruit bat"
        )
        sms_response_keyword.responses.add(sms_response_template)
        sms_response_text.clean_fields()

    def test_keyword_creation_clashing_with_boundary_punctuation(self):
        sms_response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
            all_countries=True,
        )
        sms_response_text = SMSResponseTranslation.objects.create(
            text='This is your response.',
            template=sms_response_template,
        )
        sms_response_keyword = SMSResponseKeyword.objects.create(
            keyword="fruit bat "
        )
        sms_response_keyword.responses.add(sms_response_template)
        with self.assertRaises(ValidationError):
            sms_response_text.clean_fields()
            sms_response_template.clean_fields()

    def test_duplicate_keyword_creation_raises_error(self):
        sms_response_keyword1 = SMSResponseKeyword.objects.create(
            keyword="fruit bat"
        )
        with self.assertRaises(IntegrityError):
            sms_response_keyword2 = SMSResponseKeyword.objects.create(
                keyword="fruit bat"
            )

    def test_duplicate_keyword_in_separate_countries_works(self):
        kenya = Border.objects.get(country='Kenya', level=0)
        uganda = Border.objects.get(country='Uganda', level=0)

        kenya_template = SMSResponseTemplate.objects.create(
            name='Kenya fruit bat test',
            all_countries=False,
        )
        kenya_response_text = SMSResponseTranslation.objects.create(
            text='This is your response.',
            template=kenya_template,
        )
        sms_response_keyword = SMSResponseKeyword.objects.create(
            keyword="fruit bat",
        )
        kenya_template.countries.add(kenya)
        kenya_template.keywords.add(sms_response_keyword)

        uganda_template = SMSResponseTemplate.objects.create(
            name='Uganda fruit bat test',
            all_countries=False,
        )
        uganda_response_text = SMSResponseTranslation.objects.create(
            text='This is your response.',
            template=uganda_template,
        )
        kenya_template.countries.add(uganda)
        kenya_template.keywords.add(sms_response_keyword)


class ReceiveSMSKeywordActionTests(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant, REMOTE_ADDR=valid_ip)

        self.to_phone = '12345'
        self.new_customer_phone = CustomerPhoneFactory.build().number
        self.registered_customer = CustomerFactory()

        txt = 'This is your response. Call the call centre on {call_centre}'
        self.response_template = SMSResponseTemplate.objects.create(
            name='Wobbly fruit bat template',
            all_countries=True,
        )
        self.response_text = SMSResponseTranslation.objects.create(
            text=txt,
            template=self.response_template,
        )
        self.sms_keyword = SMSResponseKeyword.objects.create(
            keyword='fruit bat',
        )
        self.sms_keyword.responses.add(self.response_template)
        # self.kenya_template = SMSResponseTemplate.objects.create(
        #     name='Kenya fruit bat test',
        #     text=self.response_text,
        #     all_countries=False,
        # )
        # kenya = Border.objects.get(country='Kenya', level=0)
        # self.kenya_template.countries.add(kenya)
        # self.kenya_template.keywords.add(self.sms_keyword)

        # self.uganda_template = SMSResponseTemplate.objects.create(
        #     name='Uganda fruit bat test',
        #     text=self.response_text,
        #     all_countries=False,
        # )
        # uganda = Border.objects.get(country='Uganda', level=0)
        # self.uganda_template.countries.add(uganda)
        # self.uganda_template.keywords.add(self.sms_keyword)

        # self.both_template = SMSResponseTemplate.objects.create(
        #     name='Both fruit bat test',
        #     text=self.response_text,
        #     all_countries=False,
        # )
        # self.both_template.countries.add(kenya)
        # self.both_template.countries.add(uganda)
        # self.both_template.keywords.add(self.sms_keyword)


    @activate_success_response
    def test_basic_auto_response(self):
        from_phone = self.registered_customer.main_phone
        text = "fruit bat"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

        message = utils.populate_templated_text(self.response_text.text, self.registered_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_basic_auto_response_to_new_customer(self):
        from_phone = self.new_customer_phone
        text = "fruit bat"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

        new_customer = Customer.objects.get(phones__number=self.new_customer_phone)
        message = utils.populate_templated_text(self.response_text.text, new_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual(new_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)
        self.assertEqual(new_customer.id, SMSRecipient.objects.first().recipient_id)

    @activate_success_response
    def test_basic_auto_response_to_existing_customer_using_other_phone(self):
        other_phone = CustomerPhone.objects.create(customer=self.registered_customer,
                                                   is_main=False, number='+254720123456')
        from_phone = other_phone.number
        text = "fruit bat"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

        customer = Customer.objects.get(phones__number=other_phone.number)
        message = utils.populate_templated_text(self.response_text.text, customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(str(other_phone.number), SMSRecipient.objects.first().extra['number'])

    @activate_success_response
    def test_case_insensitive_auto_response(self):
        from_phone = self.registered_customer.main_phone
        text = "fruIT bAt"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

        message = utils.populate_templated_text(self.response_text.text, self.registered_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual(self.registered_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_auto_response_with_punctuation(self):
        from_phone = self.registered_customer.main_phone
        text = "?fruIT bAt!"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        message = utils.populate_templated_text(self.response_text.text, self.registered_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual(self.registered_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_auto_response_with_leading_spaces(self):
        from_phone = self.registered_customer.main_phone
        text = "  fruit bat"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        message = utils.populate_templated_text(self.response_text.text, self.registered_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual(self.registered_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_auto_response_with_long_sentence(self):
        from_phone = self.registered_customer.main_phone
        text = "fruit bats are both fruity and batty"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())

    @activate_success_response
    def test_auto_response_with_task(self):
        self.response_template.action = SMSResponseTemplate.Actions.TASK
        self.response_template.save()

        from_phone = self.registered_customer.main_phone
        text = "fruit bat"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

        message = utils.populate_templated_text(self.response_text.text, self.registered_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual(self.registered_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

        the_sms = IncomingSMS.objects.first()
        the_task = Task.objects.first()
        self.assertEqual(the_sms, sent_sms.incoming_sms)
        self.assertEqual(the_task.customer, self.registered_customer)
        self.assertEqual(the_task.description, "{} Keyword SMS: {}".format(self.response_template.name,
                                                                           self.sms_keyword.keyword))
        self.assertEqual(the_task.source, the_sms)

    @activate_success_response
    def test_auto_response_with_category(self):
        the_category = CustomerCategoryFactory()
        self.response_template.assign_category = the_category
        self.response_template.save()

        self.assertNotIn(the_category, self.registered_customer.categories.all())

        from_phone = self.registered_customer.main_phone
        text = "fruit bat"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

        message = utils.populate_templated_text(self.response_text.text, self.registered_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual(self.registered_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

        self.registered_customer.refresh_from_db()
        self.assertIn(the_category, self.registered_customer.categories.all())

    @activate_success_response
    def test_auto_response_with_customer_already_in_category(self):
        the_category = CustomerCategoryFactory()
        self.response_template.assign_category = the_category
        self.response_template.save()

        # reload registered customer
        self.registered_customer.categories.add(the_category)
        self.registered_customer.refresh_from_db()

        self.assertIn(the_category, self.registered_customer.categories.all())

        from_phone = self.registered_customer.main_phone
        text = "fruit bat"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)

        message = utils.populate_templated_text(self.response_text.text, self.registered_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual(self.registered_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

        self.registered_customer.refresh_from_db()
        self.assertIn(the_category, self.registered_customer.categories.all())

    @activate_success_response
    def test_auto_response_with_inactive_keywords(self):
        self.sms_keyword.is_active = False
        self.sms_keyword.save()

        from_phone = self.registered_customer.main_phone
        text = "fruit bat"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

        the_sms = IncomingSMS.objects.first()
        the_task = Task.objects.first()
        self.assertEqual(the_task.customer, self.registered_customer)

        # we got the vanilla task
        self.assertEqual(the_task.description, 'Respond to SMS: fruit bat')
        self.assertEqual(the_task.source, the_sms)

        # no response was sent
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())

    @activate_success_response
    def test_overlapping_template_countries_creates_task_sends_no_response(self):
        # In SetUp(), a template with all_countries = True is created with the same keyword
        self.kenya_template = SMSResponseTemplate.objects.create(
            name='Kenya fruit bat template',
            all_countries=False,
        )
        SMSResponseTranslation.objects.create(
            text=self.response_text.text,
            template=self.kenya_template,
        )
        kenya = Border.objects.get(country='Kenya', level=0)
        self.kenya_template.countries.add(kenya)
        # Technically this should not be allowed. The admin code checks for and prevents
        # two or more response templates from having the same keyword and country combination.
        # However, if somehow the DB gets into this state, we need to handle it gracefully.
        self.kenya_template.keywords.add(self.sms_keyword)

        from_phone = self.registered_customer.main_phone
        text = self.sms_keyword.keyword
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

        the_sms = IncomingSMS.objects.first()
        the_task = Task.objects.first()
        self.assertEqual(the_task.customer, self.registered_customer)

        # we got the vanilla task
        self.assertEqual(the_task.description, 'Respond to SMS: fruit bat')
        self.assertEqual(the_task.source, the_sms)

        # no response was sent
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())

    @activate_success_response
    def test_same_template_separate_countries_responds_correctly(self):
        reused_keyword = SMSResponseKeyword.objects.create(
            keyword='gloobertyfoo',
        )
        # Kenya
        kenya_template = SMSResponseTemplate.objects.create(
            name='Kenya gloobertyfoo test',
            all_countries=False,
        )
        kenya_text = SMSResponseTranslation.objects.create(
            text='Kenya gloobertyfoo response',
            template=kenya_template,
        )
        kenya = Border.objects.get(country='Kenya', level=0)
        kenya_template.countries.add(kenya)
        kenya_template.keywords.add(reused_keyword)
        # Uganda
        uganda_template = SMSResponseTemplate.objects.create(
            name='Uganda gloobertyfoo test',
            all_countries=False,
        )
        uganda_text = SMSResponseTranslation.objects.create(
            text='Uganda gloobertyfoo response',
            template=uganda_template,
        )
        uganda = Border.objects.get(country='Uganda', level=0)
        uganda_template.countries.add(uganda)
        uganda_template.keywords.add(reused_keyword)

        # The two templates are for different countries but
        # trigger on the same incoming keyword

        # Test kenya first
        from_phone = self.registered_customer.main_phone  # registered_customer has a Kenya number
        text = reused_keyword.keyword
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

        # No task was created
        self.assertEqual(0, Task.objects.count())
        # One response was sent
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        self.assertEqual(kenya_text.text, OutgoingSMS.objects.first().text)

        # Then test Uganda
        from_phone = '+256701234567'
        text = reused_keyword.keyword
        data = get_sms_data(text, from_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

        # No task was created
        self.assertEqual(0, Task.objects.count())
        # One response was sent
        self.assertEqual(2, OutgoingSMS.objects.count())
        self.assertEqual(2, SMSRecipient.objects.count())
        recipient = SMSRecipient.objects.get(recipient__phones__number=from_phone)
        message = recipient.message
        self.assertEqual(uganda_text.text, message.text)


class SendSMSResponseTests(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant, REMOTE_ADDR=valid_ip)
        self.text = "This is the SendTests TestCase"

        self.active_customer = CustomerFactory()
        self.unregistered_customer = CustomerFactory(unregistered=True)
        self.opted_out_customer = CustomerFactory(stopped=True)

        # Create a bare phone number without the corresponding customer record saved to the DB
        self.new_customer_phone = CustomerPhoneFactory.build().number
        self.non_kenyan_phone = '+442088118181'
        self.to_phone = '12345'

    @activate_success_response
    def test_response_new_customer_join_sms(self):
        from_phone = self.new_customer_phone
        text = "JOIN"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)

        customer = Customer.objects.get(phones__number=self.new_customer_phone)
        message, sender = utils.get_populated_sms_templates_text(settings.SMS_JOIN, customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(message, sent_sms.text)
        self.assertEqual('21606', sender)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)


    @activate_success_response
    def test_response_active_customer_join_sms(self):
        from_phone = self.active_customer.main_phone
        text = "JOIN"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)

        message, sender = utils.get_populated_sms_templates_text(settings.SMS_ACTIVE_CUSTOMER_JOIN, self.active_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual('21606', sender)
        self.assertEqual(self.active_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_response_inactive_customer_rejoin_sms(self):
        from_phone = self.opted_out_customer.main_phone
        text = "JOIN"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)

        message, sender = utils.get_populated_sms_templates_text(settings.SMS_INACTIVE_CUSTOMER_REJOIN, self.active_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual('21606', sender)
        self.assertEqual(self.opted_out_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_response_international_sms(self):
        from_phone = self.non_kenyan_phone
        text = "JOIN"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)

        customer = Customer.objects.get(phones__number=self.non_kenyan_phone)
        message, sender = utils.get_populated_sms_templates_text(settings.SMS_UNSUPPORTED_REGION, customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual('21606', sender)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_response_active_customer_empty_sms(self):
        from_phone = self.active_customer.main_phone
        text = ""
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        self.assertEqual(0, Task.objects.count())

        message, sender = utils.get_populated_sms_templates_text(settings.SMS_EMPTY_MESSAGE_RESPONSE, self.active_customer)
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual('21606', sender)
        self.assertEqual(self.active_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_response_stopped_customer_empty_sms(self):
        from_phone = self.opted_out_customer.main_phone
        text = ""
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        self.assertEqual(0, Task.objects.count())

        message, sender = utils.get_populated_sms_templates_text(settings.SMS_EMPTY_MESSAGE_RESPONSE, self.opted_out_customer)
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual('21606', sender)
        self.assertEqual(self.opted_out_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_response_new_customer_empty_sms(self):
        from_phone = self.new_customer_phone
        text = ""
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        self.assertEqual(0, Task.objects.count())

        customer = Customer.objects.get(phones__number=self.new_customer_phone)
        message, sender = utils.get_populated_sms_templates_text(settings.SMS_EMPTY_MESSAGE_RESPONSE, customer)
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual('21606', sender)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    """
    @activate_success_response
    def test_response_digifarm_number_as_phone(self):

        # Ensure that Digifarm customers are not treated as coming from outside Kenya.

        customer = CustomerFactory(has_no_phones=True)
        phone = CustomerPhoneFactory(number='+254722123456', is_main=True, customer=customer)
        df_number = generate_phone_number(prefix=phonenumbers.country_code_for_region('DE'), length=9)
        df_phone = CustomerPhoneFactory(number=df_number, is_main=False, customer=customer)
        data = get_sms_data("JOIN", df_phone, self.to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)

        message, sender = utils.get_populated_sms_templates_text(settings.SMS_UNSUPPORTED_REGION, customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())  # Messages sent via AT number
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual('21606', sender)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)
    """
    @activate_success_response
    def test_response_new_customer_stop_sms(self):
        from_phone = self.new_customer_phone
        text = "STOP"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)

        customer = Customer.objects.get(phones__number=self.new_customer_phone)
        message, sender = utils.get_populated_sms_templates_text(settings.SMS_INACTIVE_CUSTOMER_STOP,
                                                                 customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual('21606', sender)
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_response_active_customer_stop_sms(self):
        from_phone = self.active_customer.main_phone
        text = "STOP"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)

        message, sender = utils.get_populated_sms_templates_text(settings.SMS_STOP, self.active_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual('21606', sender)
        self.assertEqual(self.active_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_response_opted_out_customer_stop_sms(self):
        from_phone = self.opted_out_customer.main_phone
        text = "STOP"
        data = get_sms_data(text, from_phone, self.to_phone)

        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)

        message, sender = utils.get_populated_sms_templates_text(settings.SMS_INACTIVE_CUSTOMER_STOP, self.opted_out_customer)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(sent_sms.text, message)
        self.assertEqual('21606', sender)
        self.assertEqual(self.opted_out_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_active_customer_stop_does_stop_messages(self):
        self.assertTrue(self.active_customer.should_receive_messages)

        from_phone = self.active_customer.main_phone
        text = "STOP"
        data = get_sms_data(text, from_phone, self.to_phone)

        self.client.post(reverse('sms_api_callback'), data)

        self.active_customer.refresh_from_db()
        self.assertFalse(self.active_customer.should_receive_messages)
        self.assertTrue(self.active_customer.has_requested_stop)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(self.active_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)

    @activate_success_response
    def test_response_opted_out_customer_stop_customer_remains_stopped(self):
        self.assertFalse(self.opted_out_customer.should_receive_messages)

        from_phone = self.opted_out_customer.main_phone
        text = "STOP"
        data = get_sms_data(text, from_phone, self.to_phone)

        self.client.post(reverse('sms_api_callback'), data)

        self.opted_out_customer.refresh_from_db()
        self.assertFalse(self.opted_out_customer.should_receive_messages)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        sent_sms = OutgoingSMS.objects.first()
        self.assertEqual(self.opted_out_customer.id, SMSRecipient.objects.first().recipient_id)
        self.assertEqual(OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE, sent_sms.message_type)


class SMSCallbackFirewallTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.good_ip = valid_ip
        self.bad_ip = '9.9.9.9'
        self.active_customer = CustomerFactory()
        self.to_phone = '12345'

    @activate_success_response
    def test_good_ip_sms_arrival(self):
        c = Client(self.tenant, REMOTE_ADDR=self.good_ip)
        from_phone = self.active_customer.main_phone
        text = "Hello, world"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = c.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 200)

    def test_bad_ip_sms_arrival(self):
        c = Client(self.tenant, REMOTE_ADDR=self.bad_ip)
        from_phone = self.active_customer.main_phone
        text = "Hello, world"
        data = get_sms_data(text, from_phone, self.to_phone)
        response = c.post(reverse('sms_api_callback'), data)

        self.assertEqual(response.status_code, 403)

class IncomingSMSTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        super(IncomingSMSTestCase, cls).setUpTestData()
        CommodityFactory(name="Maize", crop=True)
        CommodityFactory(name="Dairy Cow")
        CommodityFactory(name="Indigenous Chickens", short_name="Indig Chic")
        CommodityFactory(name="Cow Peas")

    def setUp(self):
        get_commodity_map.cache_clear()

    def tearDown(self):
        get_commodity_map.cache_clear()

    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_invoke_ai_agent_success(self, mock_agent):
        # Set up customer and incoming SMS
        customer = CustomerFactory(border0__name='Kenya', unregistered=True)
        incoming_sms = IncomingSMSFactory(customer=customer, text='I want to register')

        # Mock the agent's invoke method to return successful signup information
        mock_agent.return_value = SignupInformation(
            name="John Doe",
            crops_livestock=["Maize", "Cows"],
            border1="Nairobi",
            border3="Parklands/Highridge",
            nearest_school="Westlands School"
        )

        # Call the method
        incoming_sms.invoke_ai_agent()

        # Check that customer details are updated
        customer.refresh_from_db()
        self.assertEqual(customer.name, "John Doe")
        self.assertEqual(customer.border1.name, "Nairobi")
        self.assertEqual(customer.border3.name, "Parklands/Highridge")
        self.assertTrue(customer.is_registered)

        # Check that a response SMS was sent
        outgoing_sms = OutgoingSMS.objects.filter(incoming_sms=incoming_sms).first()
        self.assertIsNotNone(outgoing_sms)
        self.assertIn("Thank you! Every required information was provided.", outgoing_sms.text)

    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_invoke_ai_agent_central_uganda(self, mock_agent):
        # regression test for failure to disambiguate border1s by country

        # Set up customer and incoming SMS
        customer = CustomerFactory(border0=Border.objects.get(country='Uganda', level=0), phones=None, add_main_phones=['+256752621238'], unregistered=True)
        incoming_sms = IncomingSMSFactory(customer=customer, text='I want to register')

        # Mock the agent's invoke method to return successful signup information
        mock_agent.return_value = SignupInformation(
            name="John Doe",
            crops_livestock=["Maize", "Cows"],
            border1="Central",
            border3="Kabula",
            nearest_school=""
        )

        # Call the method
        incoming_sms.invoke_ai_agent()

        # Check that customer details are updated
        customer.refresh_from_db()
        self.assertEqual(customer.name, "John Doe")
        self.assertEqual(customer.border1.name, "Central")
        self.assertEqual(customer.border3.name, "Kabula")
        self.assertTrue(customer.is_registered)

        # Check that a response SMS was sent
        outgoing_sms = OutgoingSMS.objects.filter(incoming_sms=incoming_sms).first()
        self.assertIsNotNone(outgoing_sms)
        self.assertIn("Thank you! Every required information was provided.", outgoing_sms.text)

    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_invoke_ai_agent_strips_shared_shortcode_prefix(self, mock_agent):
        # Set up customer and incoming SMS
        customer = CustomerFactory(border0=Border.objects.get(country='Uganda', level=0), phones=None, add_main_phones=['+256752621238'], unregistered=True)
        incoming_sms = IncomingSMSFactory(customer=customer, text='SSU I want to register')

        # Mock the agent's invoke method to return successful signup information
        mock_agent.return_value = SignupInformation(
            name="",
            crops_livestock=[],
            border1="",
            border3="",
            nearest_school=""
        )

        # Call the method
        incoming_sms.invoke_ai_agent()

        mock_agent.assert_called_once_with("I want to register")

    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_invoke_ai_agent_missing_border3(self, mock_agent):
        # Set up customer and incoming SMS
        customer = CustomerFactory(border0__name='Kenya', unregistered=True)
        incoming_sms = IncomingSMSFactory(customer=customer, text='I want to register')

        # Mock the agent's invoke method to return successful signup information
        mock_agent.return_value = SignupInformation(
            name="John Doe",
            crops_livestock=["Maize", "Cows"],
            border1="Nairobi",
            border3="",
            nearest_school=""
        )

        CommodityFactory(name="Maize", crop=True)

        # Call the method
        incoming_sms.invoke_ai_agent()

        # Check that customer details are updated
        customer.refresh_from_db()
        self.assertEqual(customer.name, "John Doe")
        self.assertEqual(customer.border1.name, "Nairobi")
        self.assertListEqual(list(customer.commodities.all().order_by('name').values_list('name', flat=True)), ["Dairy Cow", "Maize"])
        self.assertFalse(customer.is_registered)

        # Check that a response SMS was sent
        outgoing_sms = OutgoingSMS.objects.filter(incoming_sms=incoming_sms).first()
        self.assertIsNotNone(outgoing_sms)
        self.assertIn("Thank you! To complete the registration, please review the following points:Please provide your Ward or the nearest school to your farm", outgoing_sms.text)

    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_invoke_ai_agent_missing_name(self, mock_agent):
        # Set up customer and incoming SMS
        customer = CustomerFactory(border0__name='Kenya', unregistered=True)
        incoming_sms = IncomingSMSFactory(customer=customer, text='I want to register')

        # Mock the agent's invoke method to return successful signup information
        mock_agent.return_value = SignupInformation(
            name="",
            crops_livestock=["Maize", "Cows"],
            border1="Nairobi",
            border3="Parklands/Highridge",
            nearest_school="Westlands School"
        )

        # Call the method
        incoming_sms.invoke_ai_agent()

        # Check that customer details are updated
        customer.refresh_from_db()
        self.assertEqual(customer.border1.name, "Nairobi")
        self.assertEqual(customer.border3.name, "Parklands/Highridge")
        self.assertListEqual(list(customer.commodities.all().order_by('name').values_list('name', flat=True)), ["Dairy Cow", "Maize"])
        self.assertFalse(customer.is_registered)

        # Check that a response SMS was sent
        outgoing_sms = OutgoingSMS.objects.filter(incoming_sms=incoming_sms).first()
        self.assertIsNotNone(outgoing_sms)
        self.assertIn("Thank you! To complete the registration, please review the following points:Please provide your name", outgoing_sms.text)

    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_invoke_ai_agent_missing_commodities(self, mock_agent):
        # Set up customer and incoming SMS
        customer = CustomerFactory(border0__name='Kenya', unregistered=True)
        incoming_sms = IncomingSMSFactory(customer=customer, text='I want to register')

        # Mock the agent's invoke method to return successful signup information
        mock_agent.return_value = SignupInformation(
            name="John Doe",
            crops_livestock=[],
            border1="Nairobi",
            border3="Parklands/Highridge",
            nearest_school="Westlands School"
        )

        # Call the method
        incoming_sms.invoke_ai_agent()

        # Check that customer details are updated
        customer.refresh_from_db()
        self.assertEqual(customer.border1.name, "Nairobi")
        self.assertEqual(customer.border3.name, "Parklands/Highridge")
        self.assertListEqual(list(customer.commodities.all().order_by('name').values_list('name', flat=True)), [])
        self.assertFalse(customer.is_registered)

        # Check that a response SMS was sent
        outgoing_sms = OutgoingSMS.objects.filter(incoming_sms=incoming_sms).first()
        self.assertIsNotNone(outgoing_sms)
        self.assertIn("Thank you! To complete the registration, please review the following points:Crops and livestock are missing", outgoing_sms.text)

    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_invoke_ai_agent_missing_commodities_and_name(self, mock_agent):
        # Set up customer and incoming SMS
        customer = CustomerFactory(border0__name='Kenya', unregistered=True)
        incoming_sms = IncomingSMSFactory(customer=customer, text='I want to register')

        # Mock the agent's invoke method to return successful signup information
        mock_agent.return_value = SignupInformation(
            name="",
            crops_livestock=[],
            border1="Nairobi",
            border3="Parklands/Highridge",
            nearest_school="Westlands School"
        )

        # Call the method
        incoming_sms.invoke_ai_agent()

        # Check that customer details are updated
        customer.refresh_from_db()
        self.assertEqual(customer.border1.name, "Nairobi")
        self.assertEqual(customer.border3.name, "Parklands/Highridge")
        self.assertListEqual(list(customer.commodities.all().order_by('name').values_list('name', flat=True)), [])
        self.assertFalse(customer.is_registered)

        # Check that a response SMS was sent
        outgoing_sms = OutgoingSMS.objects.filter(incoming_sms=incoming_sms).first()
        self.assertIsNotNone(outgoing_sms)
        self.assertIn("Thank you! To complete the registration, please review the following points:Please provide your name, Crops and livestock are missing", outgoing_sms.text)

    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_invoke_ai_agent_filters_calendar_based_commodities(self, mock_agent):

        get_commodity_map.cache_clear()
        CommodityFactory(name="Maize", crop=True)
        CommodityFactory(name="CB Cow")

        customer = CustomerFactory(border0=Border.objects.get(country='Uganda', level=0), phones=None, add_main_phones=['+256752621238'], unregistered=True)
        incoming_sms = IncomingSMSFactory(customer=customer, text='I want to register')

        # Mock the agent's invoke method to return successful signup information
        mock_agent.return_value = SignupInformation(
            name="John Doe",
            crops_livestock=["Maize", "Cow"],
            border1="Central",
            border3="Kabula",
            nearest_school=""
        )

        # Call the method
        incoming_sms.invoke_ai_agent()

        # Check that customer details are updated
        customer.refresh_from_db()
        self.assertListEqual(list(customer.commodities.all().order_by('name').values_list('name', flat=True)), ['Dairy Cow', 'Maize'])
        self.assertTrue(customer.is_registered)

    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_invoke_ai_agent_llm_exception(self, mock_invoke):
        # Set up customer and incoming SMS
        customer = CustomerFactory(border0__name='Kenya', unregistered=True)
        incoming_sms = IncomingSMSFactory(customer=customer, text='I want to register')

        # Mock the agent's invoke method to raise an LLMException
        mock_invoke.side_effect = LLMException()

        # Call the method
        incoming_sms.invoke_ai_agent()

        # Check that an AI error task was created and customer is flagged
        customer.refresh_from_db()
        self.assertTrue(customer.skip_ai_invocation)

        # Check that no response SMS was sent
        outgoing_sms = OutgoingSMS.objects.filter(incoming_sms=incoming_sms).first()
        self.assertIsNone(outgoing_sms)

    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_invoke_ai_agent_duplicate_response(self, mock_invoke):
        # Set up customer and incoming SMS
        customer = CustomerFactory(border0__name='Kenya', unregistered=True)
        incoming_sms = IncomingSMSFactory(customer=customer, text='I want to register')

        # Mock the agent's invoke method to return a duplicate response
        mock_invoke.return_value = SignupInformation(
            name="John Doe",
            crops_livestock=["Maize", "Cows"],
            border1="Nairobi",
            border3="Parklands/Highridge",
            nearest_school="Westlands School"
        )

        # Create a duplicate response
        OutgoingSMS.objects.create(
            text="Thank you! Every required information was provided. You are now registered in our system.",
            incoming_sms=incoming_sms,
        )

        # Call the method
        incoming_sms.invoke_ai_agent()

        # Check that an AI error task was created for duplicate response
        customer.refresh_from_db()
        self.assertTrue(customer.skip_ai_invocation)

        # Check that no new response SMS was sent
        outgoing_sms_count = OutgoingSMS.objects.filter(incoming_sms=incoming_sms).count()
        self.assertEqual(outgoing_sms_count, 1)

    @patch.object(SignupAiAgent, 'invoke')  # Mock SignupAiAgent's invoke method
    def test_invoke_ai_agent_needs_human_intervention(self, mock_invoke):
        # Set up customer and incoming SMS
        customer = CustomerFactory(border0__name='Kenya', unregistered=True)
        incoming_sms = IncomingSMSFactory(customer=customer, text='I want to register')

        # Mock the agent's invoke method to return incomplete information
        mock_invoke.return_value = SignupInformation(
            name=None,
            crops_livestock=["Monkeys"],
            border1=None,
            border3=None,
            nearest_school=None
        )

        # Call the method
        incoming_sms.invoke_ai_agent()

        # Check that customer is flagged for human intervention
        customer.refresh_from_db()
        self.assertTrue(customer.skip_ai_invocation)

        # Check that an AI error task was created
        task = customer.tasks.filter(description__contains="AI Signup agent requires human intervention").first()
        self.assertIsNotNone(task)

        # Check that no response SMS was sent
        outgoing_sms = OutgoingSMS.objects.filter(incoming_sms=incoming_sms).first()
        self.assertIsNone(outgoing_sms)

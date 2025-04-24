import logging
import re
from collections import namedtuple
from datetime import timedelta
from typing import List, Optional

from fuzzywuzzy import process as fuzz_process
import phonenumbers
import sentry_sdk

from django.conf import settings
from django.db import models
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from dateutil.relativedelta import relativedelta

from agri.constants import COMMODITY_TYPES
from agri.models import COMMODITY_MAP_OVERRIDES, get_commodity_map
from customers.constants import JOIN_METHODS, STOP_METHODS
from gateways import gateways

from core.models import TimestampedBase
from core.utils.datetime import localised_date_formatting_string
from customers.models import NPSResponse
from payments.models import FreeSubscriptionOffer, VerifyInStoreOffer, Voucher
from search.constants import ENGLISH_ANALYZER
from search.fields import ESAnalyzedTextField
from search.indexes import ESIndexableMixin
from sms import utils
from sms.agent import SignupAiAgent, LLMException, SignupInformation, AiResponseValidation
from sms.constants import (
    OUTGOING_SMS_TYPE,
    FREE_MONTHS, KENYA_COUNTRY_CODE,
    KEYWORD_SMS_DETAILS_TEMPLATE,
    RESPOND_TO_UNPARSABLE_SMS_TASK_TITLE,
    REVIEW_RESPONSE_TASK_TITLE, UGANDA_COUNTRY_CODE,
    GSM_WHITELIST_PUNCTUATION, VANILLA_SMS_DETAILS_TEMPLATE, RESPOND_TO_AI_ERROR_TASK_TITLE,
    ZAMBIA_COUNTRY_CODE,
)
from sms.models import SMSResponseKeyword, SMSResponseTemplate, OutgoingSMS, SMSRecipient
from sms.tasks import send_message
from tasks.models import Task, TaskUpdate
from world import school_matching
from world.models import Border, BorderLevelName
from world.utils import get_country_for_phone

from subscriptions.models import Subscription

__all__ = ['IncomingSMS']

logger = logging.getLogger(__name__)


class BaseSMS(models.Model):
    """ Base class for SMS messages (both incoming and outgoing). """

    GATEWAY_CHOICES = gateways.GATEWAY_CHOICES

    at = models.DateTimeField(_('At'))

    # number fields
    sender = models.CharField(_('Sender'), max_length=30)
    recipient = models.CharField(_('Recipient'), max_length=30)

    text = ESAnalyzedTextField(_('Message text'), blank=True, analyzer=ENGLISH_ANALYZER)

    gateway = models.PositiveSmallIntegerField(_('Gateway'),
                                               choices=GATEWAY_CHOICES)

    # message id assigned by gateway
    gateway_id = models.CharField(_('Gateway identifier'), max_length=100)

    class Meta:
        abstract = True


class IncomingSMS(ESIndexableMixin, TimestampedBase, BaseSMS):
    """ Stores and handles incoming SMS messages.  """
    INDEX_FIELDS = ['text', 'customer', 'id', 'created', 'last_updated', 'customer_created']
    customer = models.ForeignKey(
        'customers.Customer',
        help_text=_("The customer who had the SMS's 'from' number at the time "
                    "the SMS was received. Customer's current number may "
                    "differ from this entry's 'from' number."),
        on_delete=models.CASCADE
    )

    customer_created = models.BooleanField(
        default=False,
        help_text=_("This was the first contact with the customer, and caused "
                    "the initial creation of the customer record."))

    class Meta:
        ordering = 'at',
        verbose_name = _("Incoming SMS")

    def __init__(self, *args, **kwargs):
        """ Add default to gateway field as currently we only support AT. """
        super().__init__(*args, **kwargs)

        self._meta.get_field('gateway').default = gateways.AT

    def __str__(self):
        return str(self.at)

    def is_nps_response(self) -> OutgoingSMS:
        """
        Checks whether this could be a response to an nps survey.
        """
        # We only consider this a response if it contains mainly a number.
        # Messages longer than 10 characters could be something else.
        if len(self.text) > 10:
            return OutgoingSMS.objects.none()

        # We only consider this a response to an nps request if the
        # query was sent in the last 3 days
        earliest_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=3)
        # Retrieve the most recent nps query sent
        recently_sent = SMSRecipient.objects.filter(recipient=self.customer,
                                                    created__gte=earliest_date,
                                                    message__message_type=OUTGOING_SMS_TYPE.NPS_REQUEST,
                                                    page_index=1).order_by('-created').first()
        if not recently_sent:
            return OutgoingSMS.objects.none()

        # We only consider this a response if this is the first response since the query.
        recently_received = IncomingSMS.objects.filter(customer=self.customer,
                                                       created__gte=recently_sent.created)
        # Check if the message contains only a single number (including a minus sign for error checking later)
        msg_numbers = re.findall(r"[-\d]{1,2}", self.text)

        # If we recently sent a query and this is the first response and the response contains a number
        if recently_sent and recently_received.count() == 1 and len(msg_numbers) in (1, 2):
            # For now, simply return the most recent query
            return recently_sent.message
        return OutgoingSMS.objects.none()

    def is_query_response(self) -> OutgoingSMS:
        """
        Checks whether this could be a response to a survey or data query.
        If so, it returns the OutgoingSMS message of the potential query.
        """
        # We only consider this a response to a query if the
        # query was sent in the last 3 days and this is the
        # first customer's response since the query.
        earliest_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=3)
        # Retrieve the most recent data query sent
        recently_sent = SMSRecipient.objects.filter(recipient=self.customer,
                                                    created__gte=earliest_date,
                                                    message__message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
                                                    page_index=1).order_by('-created').first()
        if not recently_sent:
            return OutgoingSMS.objects.none()

        # Check if this message is the first received from the customer since sending the query
        recently_received = IncomingSMS.objects.filter(customer=self.customer,
                                                       created__gte=recently_sent.created)
        # If we recently sent a query and this is the first response
        if recently_sent and recently_received.count() == 1:
            # For now, simply return the most recent query
            return recently_sent.message
        return OutgoingSMS.objects.none()

    def parse_for_action(self):
        """
        Strips boundary punctuation and whitespace and then attempts to find a
        matching hard-coded response, Voucher, or SMSResponseKeyword response.

        Returns:
            A tuple of (method_name, args_list, kwargs_dict) corresponding to
            how the message should be handled.
        """

        msg = self.text.strip(GSM_WHITELIST_PUNCTUATION).upper()

        # First, attempt to match a voucher
        try:
            voucher = Voucher.objects.get(code=msg)
        except Voucher.DoesNotExist:
            pass
        else:
            return ('voucher_response', [], {'voucher': voucher})

        # If not a voucher, check if it's a response to a recent nps survey
        nps_msg = self.is_nps_response()
        if nps_msg:
            return ('query_response', [], {
                'query_response_handler': 'auto_handle_nps_response',
                'query_message': nps_msg,
            })

        # Check if it's a response to a recent query
        query_msg = self.is_query_response()
        if query_msg:
            return ('query_response', [], {
                'query_response_handler': 'auto_handle_location_response',
                'query_message': query_msg,
            })

        # Attempt to match an SMSResponseKeyword
        keyword, template = utils.match_smsresponsekeyword_and_template(msg, self.customer)
        if keyword is not None and template is not None:
            return ('keyword_response', [], {'keyword': keyword, 'template': template})

        if not settings.SIGNUP_AI_AGENT_WHITELIST_ENABLED or self.sender in settings.SIGNUP_AI_AGENT_WHITELISTED_NUMBERS:
            if not self.customer.is_registered and not self.customer.skip_ai_invocation:
                return ('invoke_ai_agent', [], {})

        # Lastly, if all lookups failed, just do the vanilla response
        return ('create_vanilla_task', [], {})

    def process(self):
        """ Attempts to parse for action, then performs that action. """
        # Early exit if it's not from a country that we support.
        # Check the phone number that this was sent from, rather than the customer's
        # main phone, because our responses will be sent to the sender number.
        phone = phonenumbers.parse(self.sender)
        if phone.country_code not in (KENYA_COUNTRY_CODE, UGANDA_COUNTRY_CODE, ZAMBIA_COUNTRY_CODE):
            return self.respond_to_unsupported_region_number()

        # Check if this is a duplicate to another message recently received from the same customer.
        duplicate_window_beginning = self.at - timedelta(hours=settings.DUPLICATE_SMS_DETECTION_HOURS)
        duplicates = IncomingSMS.objects.filter(text=self.text, customer=self.customer,
                                                at__gte=duplicate_window_beginning)
        if duplicates.count() > 1:
            # We expect one, which is self. If there are others, this is a duplicate.
            logger.debug(f"IncomingSMS.process(): DUPLICATE DETECTED: from:{phone} --> {self.text}")
            return

        method_name, args, kwargs = self.parse_for_action()
        if method_name is None:
            return

        method = getattr(self, method_name)
        if not method:
            raise Exception("Method {} not implemented".format(method_name))

        method(*args, **kwargs)

    def respond_to_unsupported_region_number(self):
        """
        Sends a response, calling `send` with the `allow_international` kwarg.
        """
        message, sender = utils.get_populated_sms_templates_text(settings.SMS_UNSUPPORTED_REGION,
                                                                 self.customer)
        kwargs = {'using_numbers': [self.sender]}
        self.create_and_send_sms_response(message, sender=sender, allow_international=True, **kwargs)

    def create_vanilla_task(self):
        """
        Creates a 'vanilla' Task.  The default action when no
        keyword, SMSResponseKeyword, or Voucher matches.
        """
        desc = RESPOND_TO_UNPARSABLE_SMS_TASK_TITLE + ': ' + self.text

        # Mark tasks for Premium subscription customers as high priority.
        # Note that fremium subscribers can have permanent subscriptions, so
        # we need to check for both active (dates) and not_permanent in order
        # to determine whether the customer has a current premium subscription.
        today = timezone.now().date()
        subs = Subscription.objects.filter(customer=self.customer,
                                           start_date__lte=today,
                                           end_date__gte=today,
                                           type__is_permanent=False)

        if subs:
            priority = 'high'
        else:
            priority = 'medium'

        task = Task.objects.create(
            customer=self.customer,
            description=desc,
            source=self,
            priority=priority)
        task.incoming_messages.add(self)
        msg = VANILLA_SMS_DETAILS_TEMPLATE.format(text=self.text)
        TaskUpdate.objects.create(
            task=task,
            message=msg,
            status=Task.STATUS.new,
        )

        if self.customer_created:
            # We treat non-keyword request from first-time phone number as both question (requiring vanilla task),
            # and a join request.
            self.respond_to_join()

    def respond_to_join(self):
        self.customer.join_method = JOIN_METHODS.SMS
        self.customer.save(update_fields=['join_method'])
        kwargs = {'using_numbers': [self.sender]}
        return self.customer.enroll(join_sms=self, **kwargs)

    def respond_to_stop(self, template: SMSResponseTemplate):
        """
        Sends a stop response to the customer, formatted according to whether
        lapsed, currently-subscribed, or new. Returns a boolean indicating success.
        """
        if template is None:
            sentry_sdk.capture_message(f"Trying to stop a customer without a STOP template")
            return False

        # If keyword is not None, then it should already be populated with the
        # correct reply message. Get the preferred language response text for this customer.
        text = utils.get_i10n_template_text(template, self.customer.preferred_language)

        # Populate any template text.
        message = utils.populate_templated_text(text, self.customer)
        sender = template.sender

        # However, if the customer sent STOP and is not subscribed, change the message
        if self.customer_created or self.customer.has_requested_stop:  # i.e. are they not currently receiving messages
            # Retrieve the corresponding response text (from db) and create a response message.
            message, sender = utils.get_populated_sms_templates_text(settings.SMS_INACTIVE_CUSTOMER_STOP, self.customer)

        # in any case we ensure that we set the opt-out flag has_requested_stop
        self.customer.has_requested_stop = True
        self.customer.stop_method = STOP_METHODS.SMS
        self.customer.stop_date = timezone.now().date()
        self.customer.save(update_fields=['has_requested_stop', 'stop_method', 'stop_date'])
        if message is not None and sender is not None:
            kwargs = {'using_numbers': [self.sender]}
            self.create_and_send_sms_response(message, sender, **kwargs)
            return True
        else:
            return False

    def voucher_response(self, voucher):
        """
        Processes a voucher by checking for validity (and sending the
        appropriate reply otherwise), then redirecting to the correct type of
        voucher response.
        """
        if not voucher.offer.is_current():
            key = settings.SMS_VOUCHER_OFFER_EXPIRED
        elif voucher.used_by is not None:
            if (voucher.used_by == self.customer
                    and isinstance(voucher.offer.specific, FreeSubscriptionOffer)):
                key = settings.SMS_VOUCHER_ALREADY_USED_BY_YOU
            else:
                key = settings.SMS_VOUCHER_ALREADY_USED
        else:
            # the voucher is valid
            if isinstance(voucher.offer.specific, VerifyInStoreOffer):
                return self.verify_in_store_voucher_response(voucher)
            elif isinstance(voucher.offer.specific, FreeSubscriptionOffer):
                return self.free_months_voucher_response(voucher)
            else:
                logger.error("Unidentified voucher type. Voucher: %d",
                             voucher.id)
                key = settings.SMS_VOUCHER_ERROR

        message, sender = utils.get_populated_sms_templates_text(key, self.customer, voucher=voucher)
        kwargs = {'using_numbers': [self.sender]}
        self.create_and_send_sms_response(message, sender, allow_international=True, **kwargs)

    def _update_customer_location(self, border3: Border):
        # If we got here, then exactly one border3 matched, so continue with auto-update
        border2 = border3.parent
        border1 = border2.parent

        customer = self.customer
        border1_name, border2_name, border3_name = BorderLevelName.objects.filter(country=customer.border0.name,
                                                                                  level__in=[1, 2, 3]).order_by('level').values_list('name', flat=True)

        if customer.border1 and customer.border1 != border1:
            logger.debug(f"Customer response is a {border3_name} ({border3.name}) that is not in their {border1_name}. Please call the customer to clarify.")
            return False, f"Customer response is a {border3_name} ({border3.name}) that is not in their {border1_name}. Please call the customer to clarify."
        if customer.border2 and customer.border2 != border2:
            logger.debug(f"Customer response is a {border3_name} ({border3.name}) that is not in their {border2_name}. Please call the customer to clarify.")
            return False, f"Customer response is a {border3_name} ({border3.name}) that is not in their {border2_name}. Please call the customer to clarify."
        if customer.border3 and customer.border3 != border3:
            logger.debug(f"Customer response is a {border3_name} ({border3.name}) that does not match the {border3_name} ({border3.name}) in our system. Please call the customer to clarify.")
            return False, f"Customer response is a {border3_name} ({border3.name}) that does not match the {border3_name} ({border3.name}) in our system. Please call the customer to clarify."

        if customer.border1 == border1 and customer.border2 == border2 and customer.border3 == border3:
            logger.debug("Response matches customer's existing record.")
            return True, "Response matches customer's existing record."

        # Update the customer's record with the new details
        customer.border1 = border1
        customer.border2 = border2
        customer.border3 = border3
        customer.location = border3.border.centroid
        customer.save(update_fields=['border0', 'border1', 'border2', 'border3', 'location'])
        logger.debug(f"Updated customer location: {customer.border1}, {customer.border2}, {customer.border3}")
        return True, "Successfully updated customer's location fields."

    def _extract_border3_from_sms_text(self, border3s: QuerySet) -> tuple[Border, int]:
        """
        Given the incoming text, try to extract the matching administrative boundary from the text
        TODO: Only works for Kenya now (our only usage of this query at the moment)
        """
        # First, add a leading space to assist the keyword regex below
        text = ' ' + self.text
        logger.debug(f"str: {text}")
        border1_name = border2_name = border3_name = None

        # Replace "sub county" and "sub-county" with "subcounty" to disambiguate
        text = re.sub('sub[- ]?county', 'subcounty', text)

        # Try to extract via keywords county, subcounty and ward
        # First try the "county is foo" variant
        # Note that this will only extract the first word of the county name
        match = re.search(r"\s+county\s+(is\s+){,1}([a-z']{3,})", text, flags=re.ASCII+re.IGNORECASE)
        if match:
            border1_name = match.groups()[1].title()
        match = re.search(r"\s+subcounty\s+(is\s+){,1}([a-z']{3,})", text, flags=re.ASCII+re.IGNORECASE)
        if match:
            border2_name = match.groups()[1].title()
        match = re.search(r"\s+ward\s+(is\s+){,1}([a-z']{3,})", text, flags=re.ASCII+re.IGNORECASE)
        if match:
            border3_name = match.groups()[1].title()

        if border1_name is None or border2_name is None or border3_name is None:
            # Next try the "foo county" variant
            # Note that this will only extract the first word of the county name
            logger.debug(f"Attempting county, subcounty, ward recognition of {text}")
            match = re.search(r"([a-z']{3,})\s+county", text, flags=re.ASCII+re.IGNORECASE)
            if match:
                border1_name = border1_name or match.groups()[0].title()
                logger.debug(f"MATCH county: {border1_name}")
            match = re.search(r"([a-z']{3,})\s+subcounty", text, flags=re.ASCII+re.IGNORECASE)
            if match:
                border2_name = border2_name or match.groups()[0].title()
                logger.debug(f"MATCH subcounty: {border2_name}")
            match = re.search(r"([a-z']{3,})\s+ward", text, flags=re.ASCII+re.IGNORECASE)
            if match:
                border3_name = border3_name or match.groups()[0].title()
                logger.debug(f"MATCH ward: {border3_name}")

        if border1_name is not None and border2_name is not None and border3_name is not None:
            border1s = Border.objects.filter(country='Kenya', level=1).values_list('name', flat=True)
            border2s = Border.objects.filter(country='Kenya', level=2).values_list('name', flat=True)
            match1, confidence1 = fuzz_process.extractOne(border1_name, border1s)
            match2, confidence2 = fuzz_process.extractOne(border2_name, border2s)
            match3, confidence3 = fuzz_process.extractOne(border3_name, border3s)
            try:
                if confidence1 >= 90 and confidence2 >= 90 and confidence3 >= 90:
                    # If we have high confidence in the recognition of all 3
                    border3 = Border.objects.get(country='Kenya', level=3,
                                                 name=match3,
                                                 parent__name=match2,
                                                 parent__parent__name=match1)
                    logger.debug(f"_extract_border3_from_sms_text: MATCH! {border3.name} in {border3.parent.name} in {border3.parent.parent.name}")
                    return border3, confidence3
                elif confidence3 > 95:
                    # Otherwise if we have a very high confidence in the recognition of border3
                    border3 = Border.objects.get(country='Kenya', level=3, name=match3)
                    logger.debug(f"_extract_border3_from_sms_text: MATCH! {border3.name} in {border3.parent.name} in {border3.parent.parent.name}")
                    return border3, confidence3
            except (Border.DoesNotExist, Border.MultipleObjectsReturned):
                # TODO: If MultipleObjectsReturned, disambiguate by recognizing another word within the ward name
                logger.debug(f"EXCEPTION")
                pass

        # If we got here, the full recognition and validation was not successful. Try to just identify a matching ward.

        # Remove 'ward', 'subcounty', 'county' words
        text = re.sub(r"[\s.,]ward[\s.,]?", " ", text, flags=re.ASCII+re.IGNORECASE)
        text = re.sub(r"[\s.,]subcounty[\s.,]?", " ", text, flags=re.ASCII+re.IGNORECASE)
        text = re.sub(r"[\s.,]county[\s.,]?", " ", text, flags=re.ASCII+re.IGNORECASE)

        # Remove conjunction words like 'and'
        text = re.sub(r"[\s.,]and[\s.,]", " ", text, flags=re.IGNORECASE)

        # Extract words of at least 3 characters (the minimum ward name length). This
        # also removes extra spaces, punctuation, etc.
        word_array = re.findall(r"[a-z']{3,}", text, flags=re.ASCII+re.IGNORECASE)
        logger.debug(f"word_array: {word_array}")
        # Try to find quality ward name matches starting from the full string down to one word, trimming from right
        for size in range(len(word_array), 0, -1):
            attempt_text = ' '.join(word_array[0:size])
            results = fuzz_process.extract(attempt_text, border3s)
            logger.debug(f"attempt_text: {attempt_text}")
            logger.debug(f"results: {results}")
            # Direction names (east/west) are a minimum of 4 chars plus space, so a min distance of 5 works well
            if results[0][1] >= 90 and results[0][1] >= results[1][1] + 5:
                logger.debug(f"success: {results}")
                logger.debug(f"results[0][0]: {results[0][0]}")
                # Success!
                logger.debug(f"_extract_border3_from_sms_text: best_score={results[0][1]}, best_match={results[0][0]}")
                border3 = Border.objects.get(country='Kenya', level=3, name=results[0][0])
                return border3, results[0][1]
            elif size == 1 and results[0][1] >= 85 and results[0][1] >= results[1][1] + 10:
                # If we're down to a one word search and found something close, use it
                logger.debug(f"success2: {results}")
                logger.debug(f"results[0][0]: {results[0][0]}")
                # Success!
                logger.debug(f"_extract_border3_from_sms_text: best_score={results[0][1]}, best_match={results[0][0]}")
                border3 = Border.objects.get(country='Kenya', level=3, name=results[0][0])
                return border3, results[0][1]
        # Try to find quality ward name matches starting from the full string down to one word, trimming from left
        for size in range(0, len(word_array)):
            attempt_text = ' '.join(word_array[size:])
            results = fuzz_process.extract(attempt_text, border3s)
            logger.debug(f"attempt_text: {attempt_text}")
            logger.debug(f"results: {results}")
            # Direction names (east/west) are a minimum of 4 chars plus space, so a min distance of 5 works well
            if results[0][1] >= 90 and results[0][1] >= results[1][1] + 5:
                logger.debug(f"success: {results}")
                logger.debug(f"results[0][0]: {results[0][0]}")
                # Success!
                logger.debug(f"_extract_border3_from_sms_text: best_score={results[0][1]}, best_match={results[0][0]}")
                border3 = Border.objects.get(country='Kenya', level=3, name=results[0][0])
                return border3, results[0][1]
            elif size == 1 and results[0][1] >= 85 and results[0][1] >= results[1][1] + 10:
                # If we're down to a one word search and found something close, use it
                logger.debug(f"success2: {results}")
                logger.debug(f"results[0][0]: {results[0][0]}")
                # Success!
                logger.debug(f"_extract_border3_from_sms_text: best_score={results[0][1]}, best_match={results[0][0]}")
                border3 = Border.objects.get(country='Kenya', level=3, name=results[0][0])
                return border3, results[0][1]

        return Border.objects.none(), 0

    def auto_handle_nps_response(self, query_message: OutgoingSMS) -> tuple[bool, str]:
        """
        Tries to handle the customer's response to our nps query automatically.
        Returns a boolean indicating success as well as a message to highlight
        to customer care agents regarding what they need to do.
        """
        logger.debug(f"auto_handle_nps_response({query_message.text}) ---> {self.text}")

        # Check if the message contains only a single number (including a minus sign for error checking later)
        # Responses may include a fraction, e.g. 9/10
        msg_numbers = re.search(r"(-?\d{1,2})\s*(?:/\s*10)?", self.text).groups()

        # An NPS response must contain a number of 1 or 2 digits
        if msg_numbers is None or len(msg_numbers) == 0:
            return False, "No numbers found in NPS response."
        elif int(msg_numbers[0]) < 0 or int(msg_numbers[0]) > 10:
            return False, "Invalid NPS number."
        elif len(msg_numbers) > 1:
            return False, "Too many numbers found in NPS response."

        # If we got here, then exactly one NPS response value was recognized
        nps_score = msg_numbers[0]

        logger.debug(f"NPS: raw={self.text}, recorded={nps_score}")

        nps_record = NPSResponse.objects.create(
            score=nps_score,
            raw_input=self.text,
            customer=self.customer,
        )

        return True, f"Recorded NPS response: {nps_score}"

    def auto_handle_location_response(self, query_message: OutgoingSMS) -> tuple[bool, str]:
        """
        Tries to handle the customer's response to our query automatically.
        Returns a boolean indicating success as well as a message to highlight
        to customer care agents regarding what they need to do.
        """
        logger.debug(f"auto_handle_location_response({query_message.text}) ---> {self.text}")

        # Query responses must be at least 3 chars in length, ignoring punctuations and spaces
        if not re.findall(r"[a-z']{3,}", self.text, flags=re.ASCII+re.IGNORECASE):
            return False, "Too short to be a query response."

        # Construct a set of border3 choices.
        # First, get list of all border3 names in the customer's country
        if self.customer.border0:
            border3s = Border.objects.filter(country=self.customer.border0, level=3)
        else:
            phone = self.customer.main_phone
            if phone.country_code == KENYA_COUNTRY_CODE:
                self.customer.border0 = Border.objects.get(country='Kenya', level=0)
                border3s = Border.objects.filter(country='Kenya', level=3)
            elif phone.country_code == UGANDA_COUNTRY_CODE:
                self.customer.border0 = Border.objects.get(country='Uganda', level=0)
                border3s = Border.objects.filter(country='Uganda', level=3)
            elif phone.country_code == ZAMBIA_COUNTRY_CODE:
                self.customer.border0 = Border.objects.get(country='Zambia', level=0)
                border3s = Border.objects.filter(country='Uganda', level=3)
            else:
                return False, "Cannot determine customer's country"

        border3, confidence = self._extract_border3_from_sms_text(border3s.values_list('name', flat=True))

        if not border3:
            return False, "Ward not found"

        # If we got here, then exactly one border3 matched, so continue with auto-update

        updated, message = self._update_customer_location(border3)
        if updated:
            msg = f"auto_handle_location_response SUCCESS({confidence}%) ({self.text}) ---> {border3.name}, " \
                  f"{border3.parent.name}, {border3.parent.parent.name}"
            logger.debug(msg)
            if confidence < 90:
                sentry_sdk.capture_message(msg)
        return updated, message

    def query_response(self, query_message: OutgoingSMS, *args, **kwargs):
        """
        Tries to auto-interpret the SMS query response. If that fails,
        create a Task for a CCO to review the response.
        """
        method_name = kwargs.pop('query_response_handler', None)

        if method_name is None:
            raise ValueError(f"No handler for query_response: {query_message.text} --> {self.text}")

        method = getattr(self, method_name)
        if not method:
            raise Exception("Method {} not implemented".format(method_name))

        handled, auto_message = method(query_message, *args, **kwargs)
        if handled:
            # Automation handled this one so no need to create an agent Task
            return

        logger.debug(f"query_response({query_message.id},{self.id}: failure ({auto_message}): {query_message.text} ---> {self.text}")

        desc = f"{REVIEW_RESPONSE_TASK_TITLE}: \nQuery: {query_message.text} \n--->Customer Response: {self.text}"

        # Create a task for the CCO to review, where the source GFK is
        # the query, and the incoming_messages has their response
        task = Task.objects.create(
            customer=self.customer,
            description=desc,
            source=query_message)
        task.incoming_messages.add(self)
        # Create a TaskUpdate to record this state change
        msg = VANILLA_SMS_DETAILS_TEMPLATE.format(text=self.text)
        TaskUpdate.objects.create(
            task=task,
            message=msg,
            status=Task.STATUS.new,
        )

    def create_keyword_task(self, keyword: SMSResponseKeyword, template: SMSResponseTemplate, errors: str = None):
        task = Task.objects.create(
            customer=self.customer,
            description="{} Keyword SMS: {}".format(template.name, keyword.keyword),
            source=self)
        task.incoming_messages.add(self)
        response_name = template.name if template else _("No")
        msg = KEYWORD_SMS_DETAILS_TEMPLATE.format(
            text=self.text,
            keyword=keyword.keyword,
            response_name=response_name,
        )
        TaskUpdate.objects.create(
            task=task,
            message=msg,
            status=Task.STATUS.new,
        )
        if errors:
            msg = "Error when sending response: {}".format(errors)
            TaskUpdate.objects.create(task=task, message=msg)

    def keyword_response(self, keyword: SMSResponseKeyword, template: SMSResponseTemplate):
        """
        Processes a message which matches an SMSResponseKeyword by returning
        the keyword's SMSResponseTemplate, and optionally creating a task.
        """

        # Get the country of the sender
        country = get_country_for_phone(self.customer.main_phone)

        errors = None
        template_name = template.name
        create_task = template.action == SMSResponseTemplate.Actions.TASK

        if template_name in (settings.SMS_STOP, settings.SMS_STOP + f"_{country.name}"):
            handled = self.respond_to_stop(template)
            # If respond_to_stop didn't work, create a task for an agent to investigate
            if not handled:
                create_task = True  # Handled below
        elif template_name in (settings.SMS_JOIN, settings.SMS_JOIN + f"_{country.name}"):
            self.respond_to_join()
            return
        else:
            # Get the preferred language response text for this customer.
            text = utils.get_i10n_template_text(template, self.customer.preferred_language)
            message = utils.populate_templated_text(text, self.customer)
            kwargs = {'using_numbers': [self.sender]}
            errors = self.create_and_send_sms_response(message, template.sender, **kwargs)
            # If something went wrong, create a task for an agent to investigate
            if errors:
                create_task = True  # Handled below

        category = template.assign_category
        if category is not None:
            self.customer.categories.add(category)

        if create_task:
            self.create_keyword_task(keyword, template, errors)

    def free_months_voucher_response(self, voucher):
        """
        Processes a valid free-months voucher by adding the corresponding
        free subscription to the customer's account.

        If the customer is new, we first schedule them for the standard
        respond_to_join process, then annotate the task to state that the
        voucher has already been applied in addition to the default free
        period.
        """
        if self.customer.never_subscribed:
            # customer is new; first send the 'join' SMS response
            task = self.respond_to_join()
            # and automatically create their subscription straight away with
            # the standard initial free trial
            self.customer.extend_subscription(
                relativedelta(months=FREE_MONTHS))
        else:
            # customer is current/lapsed; handle everything automatically, no
            # need for a task
            task = None

        # now add the voucher to their subscription
        self.customer.extend_subscription(
            relativedelta(months=voucher.offer.specific.months))
        voucher.used_by = self.customer
        voucher.save(update_fields=['used_by'])

        if task:
            # clunky control flow, but we're back to the new customer case
            # after having determined their eventual subscription end date
            sub_end_date = self.customer.subscription.latest(
                'end_date').end_date.strftime(localised_date_formatting_string())
            msg = (
                "Customer signed up using single-use voucher '{code}' "
                "worth {months} months.\n\nThe default {free}-month "
                "introductory subscription has *already* been applied, in "
                "addition to the {months}-month subscription from the "
                "voucher.\n\nThe customer's subscription will now end on "
                "{end_date}."
            ).format(
                code=voucher.code,
                months=voucher.offer.specific.months,
                free=FREE_MONTHS,
                end_date=sub_end_date
            )
            TaskUpdate.objects.create(task=task, message=msg)

        message, sender = utils.get_populated_sms_templates_text(settings.SMS_FREE_MONTHS_VOUCHER_ACCEPTED,
                                                                 self.customer, voucher=voucher)
        kwargs = {'using_numbers': [self.sender]}
        self.create_and_send_sms_response(message, sender, allow_international=True, **kwargs)

    def verify_in_store_voucher_response(self, voucher):
        """
        Processes a valid verify-in_store voucher by marking the voucher as
        used, and responding with the voucher offer's confirmation message.
        """
        voucher.used_by = self.customer
        voucher.save(update_fields=['used_by'])
        kwargs = {'using_numbers': [self.sender]}
        self.create_and_send_sms_response(voucher.offer.specific.confirmation_message,
                                          sender=settings.SMS_SENDER_VOUCHER_DEFAULT,
                                          allow_international=True,
                                          **kwargs)

    def create_and_send_sms_response(self, message: str, sender: str, **kwargs):
        """
        The ultimate destination of most methods here. Note that we set the
        exclude_stopped_customers kwarg to default to False, as we almost always
        want auto-response messages to be sent to anyone, but still permit this
        to be overridden.
        """
        esc = kwargs.pop('exclude_stopped_customers', False)
        response = OutgoingSMS.objects.create(incoming_sms=self,
                                              text=message,
                                              time_sent=timezone.now(),
                                              message_type=OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE)
        send_message.delay(response.id, [self.customer.id],  sender=sender, exclude_stopped_customers=esc, **kwargs)

    def should_index(self):
        return True

    def strip_prefix(self, text) -> str:
        """
        Strips country specific prefixes required as a result of our using a
        shared code in the applicable countries.
        """
        country = self.customer.border0.name
        if country == "Uganda":
            return re.sub('^ssu', '', text, flags=re.IGNORECASE).strip()
        if country == 'Zambia':
            return re.sub('^mu', '', text, flags=re.IGNORECASE).strip()

        return text


    def invoke_ai_agent(self):
        country = self.customer.border0.name
        agent = SignupAiAgent(country)
        try:
            signup_information: SignupInformation = agent.invoke(self.strip_prefix(self.text))
        except LLMException:
            self.create_ai_error_task("AI could not generate a suitable Answer")
            return

        response = self.update_customer_information(signup_information)
        if not response:
            return

        if self.is_duplicate_response(response):
            self.create_ai_error_task("Duplicate response generated")
            return

        self.customer.save()

        # Pull the sender from the JOIN response template even though we don't
        # need the template itself.
        _, sender = utils.get_populated_sms_templates_text(settings.SMS_JOIN,
                                                           self.customer)
        self.create_and_send_sms_response(response, sender)

    def is_duplicate_response(self, response: str):
        duplicates = OutgoingSMS.objects.filter(text=response, incoming_sms__customer=self.customer)

        if duplicates.count() > 0:
            logger.warning(f"AI INVOCATION: DUPLICATE RESPONSE DETECTED --> ASK FOR HUMAN HElP")
            return True

        return False

    def create_ai_error_task(self, error: str):
        """
        Creates a Task for when the AI agent requires human intervention due to error or customer request.
        """
        self.customer.skip_ai_invocation = True
        self.customer.save(update_fields=['skip_ai_invocation'])

        desc = RESPOND_TO_AI_ERROR_TASK_TITLE + ': ' + error

        # Use the Subscription model to check if the customer is premium.
        if Subscription.is_premium_customer(self.customer):
            priority = 'high'
        else:
            priority = 'medium'

        task = Task.objects.create(
            customer=self.customer,
            description=desc,
            source=self,
            priority=priority
        )

        for in_msg in self.customer.incomingsms_set.iterator():
            task.incoming_messages.add(in_msg)

        msg = VANILLA_SMS_DETAILS_TEMPLATE.format(text=self.text)
        TaskUpdate.objects.create(
            task=task,
            message=msg,
            status=Task.STATUS.new,
        )

    def update_customer_information(self, signup_information: SignupInformation) -> Optional[str]:
        response_list = []

        # Name
        name = signup_information.name or self.customer.name
        if name:
            self.customer.name = name
        else:
            response_list.append("Please provide your name")

        # Commodities
        commodity_validation = self.complete_customer_commodities(signup_information.crops_livestock)
        if commodity_validation.needs_human_intervention:
            logger.info("SigunupAIAgent requires human intervention", commodity_validation.error)
            self.create_ai_error_task(error=commodity_validation.error)
            return None
        if not commodity_validation.is_complete:
            response_list.append(commodity_validation.error)

        # Border1 and Border3
        border1_validation = self.complete_customer_border1(signup_information.border1)
        border3_validation = self.complete_customer_border3(signup_information.border3, signup_information.nearest_school, self.customer.border1)
        if border1_validation.needs_human_intervention:
            logger.info("SigunupAIAgent requires human intervention", border1_validation.error)
            self.create_ai_error_task(error=border1_validation.error)
            return None
        if border3_validation.needs_human_intervention:
            logger.info("SigunupAIAgent requires human intervention", border3_validation.error)
            self.create_ai_error_task(error=border3_validation.error)
            return None
        if not border1_validation.is_complete:
            response_list.append(border1_validation.error)
        if not border3_validation.is_complete:
            response_list.append(border3_validation.error)

        if len(response_list) == 0:
            self.customer.is_registered = True
            return "Thank you! Every required information was provided. You are now registered in our system."
        if len(response_list) == 4:
            # If we weren't able to determine any fields chances are the customer's message wasn't an attempted JOIN
            # so respond with the default JOIN response.
            message, __ = utils.get_populated_sms_templates_text(settings.SMS_JOIN,
                                                            self.customer)
            return message


        return f"Thank you! To complete the registration, please review the following points:{', '.join(response_list)}"

    def complete_customer_commodities(self, commodities_raw: List[str]) -> AiResponseValidation:
        if self.customer.commodities.exists():
            return AiResponseValidation(True)

        # no commodities were provided
        if not commodities_raw:
            return AiResponseValidation(False, error="Crops and livestock are missing") # ask user for completion

        crops_map = get_commodity_map(COMMODITY_TYPES.CROP)
        livestock_map = get_commodity_map(COMMODITY_TYPES.LIVESTOCK)
        combined_map = {k: v for k, v in (crops_map | livestock_map).items() if not k.startswith("cb ")}

        # First attempt to look up commodities based on the override map.
        crops_livestock_matched = []
        commodities_lowered = list(map(lambda s: s.lower(), commodities_raw))
        for c in commodities_lowered[:]:
            if c in COMMODITY_MAP_OVERRIDES:
                crops_livestock_matched.append((COMMODITY_MAP_OVERRIDES[c], 100))
                commodities_lowered.remove(c)

        crops_livestock_matched.extend([
            fuzz_process.extractOne(c, combined_map.keys(), score_cutoff=85) for c in commodities_lowered
        ])


        # find unmatched commodities
        commodities_unmatched = [first for first, _ in filter(lambda i: None in i, zip(commodities_raw, crops_livestock_matched))]
        if commodities_unmatched:
            return AiResponseValidation(
                False,
                needs_human_intervention=True,
                error=f"The following commodities could not be matched: {', '.join(commodities_unmatched)}"
            )

        commodities_matched = [combined_map.get(tup[0]) for tup in crops_livestock_matched if tup is not None]
        self.customer.commodities.set(commodities_matched)

        return AiResponseValidation(True)

    def complete_customer_border1(self, border1_raw: Optional[str]) -> AiResponseValidation:
        if self.customer.border1:
            return AiResponseValidation(True)

        border1_level_name = BorderLevelName.objects.get(country=self.customer.border0.name, level=1).name

        # No border1 was provided
        if not border1_raw:
            return AiResponseValidation(False, error=f"{border1_level_name} is missing")

        border1s = Border.objects.filter(country=self.customer.border0.name, level=1).values_list('name', flat=True)
        res = fuzz_process.extractOne(
            border1_raw,
            border1s,
        )
        # No match found
        if not res or res[1] < 90:
            return AiResponseValidation(False, needs_human_intervention=True, error=f"{border1_raw} could not be matched as a valid {border1_level_name}")

        border1_matched = Border.objects.get(country=self.customer.border0.name, name=res[0], level=1)
        self.customer.border1 = border1_matched
        return AiResponseValidation(True)

    def complete_customer_border3(self, border3_raw: Optional[str], nearest_school_raw: Optional[str], border1: Optional[Border]) -> AiResponseValidation:
        if self.customer.border3:
            return AiResponseValidation(True)

        customer_country = self.customer.border0.name
        border1_level_name = BorderLevelName.objects.get(country=customer_country, level=1).name
        border3_level_name = BorderLevelName.objects.get(country=customer_country, level=3).name

        # School matching is currently only enabled in Kenya
        has_school_matching_enabled = customer_country == "Kenya"

        # for Uganda if no county was provided
        if not has_school_matching_enabled and not border3_raw:
            return AiResponseValidation(False, error="County is missing")

        # for Kenya if no ward and no school was provided
        if not border3_raw and not nearest_school_raw:
            return AiResponseValidation(False, error="Please provide your Ward or the nearest school to your farm")

        # no border1 was given but is required for border3
        if not border1:
            return AiResponseValidation(False, error=f"Please provide {border3_level_name} AND {border1_level_name}")

        if not border3_raw and has_school_matching_enabled:
            border3_raw = self._infer_ward_from_school(nearest_school_raw, border1)
            if not border3_raw:
                return AiResponseValidation(False, needs_human_intervention=True,
                                            error=f"{nearest_school_raw} could not be matched to a school from our list")

        border3s = Border.objects.filter(country=self.customer.border0.name, level=3).values_list('name', flat=True)
        res = fuzz_process.extractOne(
            border3_raw,
            border3s,
        )
        # No match found
        if not res or res[1] < 90:
            return AiResponseValidation(False, needs_human_intervention=True, error=f"{border3_raw} could not be matched to a valid {border3_level_name}")

        border3_matched = Border.objects.get(country=self.customer.border0.name, name=res[0], level=3)
        border2_matched = border3_matched.parent
        border1_matched = border2_matched.parent

        # border1 and border3 do not match
        if border1 and border1_matched != border1:
            return AiResponseValidation(False, needs_human_intervention=True, error=f"Border3 ({border3_matched.name}) and Border1 ({border1.name}) do not match")


        self.customer.border3 = border3_matched
        self.customer.border2 = border2_matched
        self.customer.border1 = border1_matched
        return AiResponseValidation(True)

    @staticmethod
    def _infer_ward_from_school(nearest_school_raw: str, county: Optional[Border]) -> Optional[str]:
        if not county:
            return None
        df_matches = school_matching.get_matcher().match_df(nearest_school_raw, n=1, county=county.name)
        school: namedtuple('School', ['name', 'County', 'SUB_COUNTY', 'Ward', 'score']) = list(df_matches.itertuples(index=False))[0]

        if school.score < 0.85:
            return None

        return school.Ward


import hashlib
import hmac
import json
import logging
import re
from urllib.parse import urljoin
from xml.dom.minidom import Document

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.utils import timezone
from django.views.generic import FormView, View

import phonenumbers
import pusher
import sentry_sdk
from rest_framework.renderers import JSONRenderer
from sentry_sdk import capture_message

from callcenters.models import CallCenter
from calls import constants
from calls.forms import ChoosePhoneForm
from calls.models import Call, CallCenterPhone, PusherSession
from calls.serializers import CallSerializer, SimpleCallSerializer
from core.utils.clients import client_setting
from customers.constants import JOIN_METHODS
from customers.models import Customer, CustomerPhone
from sms import utils as smsutils
from sms.constants import (KENYA_COUNTRY_CODE, OUTGOING_SMS_TYPE,
                           UGANDA_COUNTRY_CODE, ZAMBIA_COUNTRY_CODE)
from sms.models import OutgoingSMS
from sms.tasks import send_message
from world.models import Border
from world.utils import get_country_for_phone

logger = logging.getLogger(__name__)


class CallsIndexFormView(FormView):
    """
    The index of the call center. This is a FormView because on GET abs
    choose phone page will be selected (to allow the operator to choose the
    phone he's using). On POST (and form_valid) the normal index will be
    displayed after creating the operator's PusherSession.

    Warning: This form won't redirect on POST - however this seems to be the
    best way to implement this.
    """
    template_name = 'calls/form.html'
    form_class = ChoosePhoneForm

    def form_valid(self, form):
        phone = form.cleaned_data['phone']

        if form.cleaned_data.get('connect_anyway'):
            # If the user checked connect_anyway we need to clear/finish all
            # the previous session with:
            # a. The phone he is using
            # b. His username. This is needed to have consistency on empty call
            #    center checks
            (PusherSession.objects.filter(Q(call_center_phone=phone) | Q(operator=self.request.user))
                                  .update(finished_on=timezone.now()))

        PusherSession.objects.create(
            call_center_phone=phone, operator=self.request.user
        )

        return render(self.request, 'calls/index.html',
                      self.get_context_data())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'pusher_api_key': client_setting('pusher_key'),
            'cc_channel_name': constants.CC_CHANNEL_NAME,
            'new_call_event_name': constants.NEW_CALL_EVENT_NAME,
            'connected_event_name': constants.CONNECTED_EVENT_NAME,
            'hang_call_event_name': constants.HANG_CALL_EVENT_NAME,
        })

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class PusherApiCallbackView(View):
    http_method_names = ('post', 'options',)

    def post(self, request, *args, **kwargs):
        data = request.read()

        # We always compute the hmac of data and call compare_digest to reduce
        # vulnerability to timing attacks
        sig = request.META['HTTP_X_PUSHER_SIGNATURE']
        computed_sig = hmac.new(client_setting('pusher_secret').encode(),
                                data,
                                hashlib.sha256).hexdigest()
        sigs_match = hmac.compare_digest(sig, computed_sig)

        # Auth 1
        if request.META['HTTP_X_PUSHER_KEY'] != client_setting('pusher_key'):
            return HttpResponseForbidden()

        # Auth 2
        if not sigs_match:
            return HttpResponseForbidden()

        # Ok we got the Call from Pusher
        json_data = json.loads(data)

        for ev in json_data['events']:
            if ev['name'] == 'member_removed':
                (PusherSession.objects.filter(pusher_session_key=ev['user_id'])
                                      .update(finished_on=timezone.now()))

        return HttpResponse('')


class VoiceApiCallbackView(View):
    # TODO: This much of the logic in this view should be abstracted into
    # gateways. Business logic is far too tightly coupled to parsing
    # webhook callbacks.

    http_method_names = ('post', 'options',)

    def handle_voice_options(self):
        data = self.request.POST
        call = Call()
        call.is_active = (data['isActive'] == '1')
        call.provided_id = data['sessionId']
        call.direction = data['direction']
        call.destination_number = data.get('destinationNumber')

        caller_number = data.get('callerNumber')
        if not caller_number.startswith('+'):
            orig_number = caller_number
            if caller_number.startswith('00'):
                # If an international call (e.g. from a neighboring country)
                caller_number = re.sub('^00', '+', caller_number)
                logger.info(f"International number detected and corrected: {orig_number} -> {caller_number}")
                capture_message(f"International number detected and corrected: {orig_number} -> {caller_number}")
            else:
                # If it doesn't start with 00 or +, assume it's a local Kenya number.
                # AfricasTalking used to have a problem that occasionally sent us numbers this way.
                # If this is still happening, we should probably create a phonenumber object and
                # validate the number that way. For now, it seems overkill.
                caller_number = '+254' + caller_number
                logger.info(f"Local number detected and corrected: {orig_number} -> {caller_number}")
                capture_message(f"Local number detected and corrected: {orig_number} -> {caller_number}")

        call.caller_number = caller_number
        call.recording_url = data.get('recordingUrl')
        call.duration = data.get('durationInSeconds')
        call.cost = data.get('amount')
        call.duration_in_queue = data.get('queueDurationInSeconds')
        call.dequeued_to_phone_number = data.get('dequeuedToPhoneNumber')
        call.dequeued_to_session_id = data.get('dequeuedToSessionId')
        self.temp_call = call

    def route_call(self):
        methods = {
            client_setting('voice_queue_number'): self.process_call_to_queue_number,
            client_setting('voice_dequeue_number'): self.process_call_to_dequeue_number,
        }
        return methods[self.temp_call.destination_number]()

    def process_dequeued_to_phone_number(self):
        """ Handles a 'dequeued' confirmation POST request. """
        # Dequeue request. The call (identified by provided_id) has been
        # connected to the CCO identified by the dequeued_to_session_id
        # value.
        try:
            active_call = (Call.objects.active()
                                       .get(provided_id=self.temp_call.provided_id))
        except Call.DoesNotExist:
            msg = (f"Dequeue response came for a customer call which "
                   f"we have no record of: {self.temp_call.provided_id}, {self.temp_call.caller_number}.")
            logger.debug(msg, extra={'extra_vars': self.temp_call,
                                     'request': self.request})
            sentry_sdk.capture_message(msg)
            return ''
        except Call.MultipleObjectsReturned:
            msg = (f"Multiple calls found for the current dequeue POST "
                   f"request. Clearing their values, but we should not have "
                   f"gotten here: {self.temp_call.provided_id}, {self.temp_call.caller_number}.")
            logger.debug(msg, extra={'extra_vars': self.temp_call,
                                     'request': self.request})
            sentry_sdk.capture_message(msg)
            calls = (Call.objects.active()
                                 .filter(provided_id=self.temp_call.provided_id)
                                 .order_by('-created_on'))

            # We presume the most recent call is the active call
            active_call = calls.first()

            # and hang up the rest without recording call details
            for call in calls[1:]:
                call.hangup()

        dequeued_to_id = self.temp_call.dequeued_to_session_id
        try:
            cco = (PusherSession.objects.connected()
                                        .get(provided_call_id=dequeued_to_id)
                                        .operator)
        except PusherSession.DoesNotExist:
            msg = (f"Dequeue confirmation request reports dequeuing to CCO "
                   f"session that doesn't exist: {self.temp_call.provided_id}, {self.temp_call.caller_number}.")
            logger.debug(msg, extra={'request': self.request})
            sentry_sdk.capture_message(msg)
            raise

        active_call.connect(cco)
        self.notify_pusher_connect_call(active_call)

        return ''

    def process_call_to_queue_number(self):
        """ Handles API requests for incoming calls to the call centre. """
        # Handle and return non-active (hanged up) calls
        if not self.temp_call.is_active:
            return self.process_customer_hanged_call()

        # Handle 'dequeued' confirmation POST request.
        if self.temp_call.dequeued_to_phone_number:
            return self.process_dequeued_to_phone_number()

        try:
            customer = Customer.objects.get(phones__number=self.temp_call.caller_number)
        except Customer.MultipleObjectsReturned:
            # Should not be possible, but to be safe, pick one at random and log the error.
            sentry_sdk.capture_message(f"Multiple customers found for phone {self.temp_call.caller_number}")
            customer = Customer.objects.filter(phones__number=self.temp_call.caller_number).first()
        except Customer.DoesNotExist:
            # Guess the country by the country code of the phone number
            try:
                country = get_country_for_phone(self.temp_call.caller_number)
                border0 = country
            except ValueError:
                border0 = None
            except phonenumbers.NumberParseException:
                if str(self.temp_call.caller_number).startswith(f"+{KENYA_COUNTRY_CODE}"):
                    border0 = Border.objects.filter(country='Kenya',
                                                    level=0).first()  # Avoid a potential DoesNotExist exception
                elif str(self.temp_call.caller_number).startswith(f"+{UGANDA_COUNTRY_CODE}"):
                    border0 = Border.objects.filter(country='Uganda',
                                                    level=0).first()  # Avoid a potential DoesNotExist exception
                elif str(self.temp_call.caller_number).startswith(f"+{ZAMBIA_COUNTRY_CODE}"):
                    border0 = Border.objects.filter(country='Zambia',
                                                    level=0).first()  # Avoid a potential DoesNotExist exception
                else:
                    border0 = None

            customer = Customer.objects.create(join_method=JOIN_METHODS.CALL,
                                               border0=border0)
            phone = CustomerPhone.objects.create(number=self.temp_call.caller_number,
                                                 is_main=True, customer=customer)
            # If new customer calls are accepted (ACCEPT_ONLY_REGISTERED_CALL=False), send the
            # new customer a message requesting that they initiate a USSD session so that we can
            # gather their relevant details
            if customer and customer.can_access_call_centre and customer.should_receive_messages:
                message, sender, create_task = \
                    smsutils.get_populated_sms_templates_text_and_task(settings.SMS_JOIN, customer=customer)
                sms = OutgoingSMS.objects.create(text=message,
                                                 message_type=OUTGOING_SMS_TYPE.NEW_CUSTOMER_RESPONSE)
                send_message.delay(sms.id, [customer.id], sender=sender)

        self.temp_call.customer = customer
        self.temp_call.call_center = customer.call_center
        self.temp_call.save()

        if not customer.can_access_call_centre:
            return self.create_disallowed_customer_response()

        self.handle_previously_active_calls(customer,
                                            self.temp_call.provided_id)

        # Check if there is an empty call center
        if PusherSession.objects.empty_call_center():
            return self.create_empty_call_center_response()

        self.notify_pusher_new_call(self.temp_call)
        return self.create_queue_response()

    def handle_previously_active_calls(self, customer, provided_id):
        """
        Check if we got a call from a customer phone number that *already*
        exists in our queue!  Best explanation for this is that the first POST
        request, which we responded to successfully, failed later down the line
        at the telecoms provider's end.
        """
        prev_active_calls = (Call.objects.active()
                                         .filter(customer=customer)
                                         .exclude(provided_id=provided_id))
        if prev_active_calls.exists():
            # This is an error: let's mark previous matches as inactive
            # and continue with the current call.
            for previous in prev_active_calls:
                previous.hangup()

            call_count = prev_active_calls.count()
            msg = (f"Incoming call from active customer who already has {call_count} "
                   f"call(s) in the queue: {provided_id}, {self.temp_call.caller_number}..")
            logger.debug(msg, extra={'extra_vars': self.temp_call,
                                     'request': self.request})
            # sentry_sdk.capture_message(msg)

    def process_customer_hanged_call(self):
        """ Processes hanged call to the call centre. """
        caller_number = self.temp_call.caller_number
        try:
            active_call = (Call.objects.active()
                                       .get(caller_number=caller_number))
        except Call.DoesNotExist:
            # This can happen, for example, if the original incoming call POST request was never
            # received, which can happen if the server is overloaded or if there's a network or aws issue.
            msg = (f"Hang up response came about a customer call which "
                   f"we have no record of: {caller_number}.")
            logger.debug(msg, extra={'extra_vars': self.temp_call,
                                     'request': self.request})
            # sentry_sdk.capture_message(msg)
            return ''
        except Call.MultipleObjectsReturned:
            msg = (f"Multiple calls found for the current hang-up POST "
                   f"request. Clearing their values, but we should not have "
                   f"gotten here: {caller_number}.")
            logger.warning(msg, extra={'extra_vars': self.temp_call,
                                       'request': self.request})
            sentry_sdk.capture_message(msg)

            calls = (Call.objects.active()
                                 .filter(caller_number=caller_number)
                                 .order_by('-created_on'))

            # We presume the most recent call is the active call
            active_call = calls.first()

            # and hang up the rest without recording call details
            for call in calls[1:]:
                call.hangup()

        # Hangup the call and record the call details
        active_call.hangup(commit=False)
        active_call.cost = self.temp_call.cost
        active_call.duration = self.temp_call.duration
        active_call.duration_in_queue = self.temp_call.duration_in_queue
        active_call.recording_url = self.temp_call.recording_url
        active_call.save()

        self.notify_pusher_hang_call(active_call)

        return ''

    def process_call_to_dequeue_number(self):
        # We only respond to calls to this number from active CallCentrePhones.
        # NOTE: This doesn't necessarily imply they're associated with a
        # currently logged-in pusher session.
        caller_number = self.temp_call.caller_number
        if not CallCenterPhone.objects.is_active_phone(caller_number):
            return self.create_reject_response()

        provided_id = self.temp_call.provided_id
        if self.temp_call.is_active:
            return self.process_active_call_to_dequeue_number(caller_number,
                                                              provided_id)
        else:
            return self.process_cco_dequeue_hangup(provided_id)

    def process_cco_dequeue_hangup(self, provided_id):
        """
        Called when the CCO has hung up from the dequeue number to unset the
        current PusherSession's provided call id.
        """
        try:
            pusher_session = PusherSession.objects.get(provided_call_id=provided_id)
        except PusherSession.DoesNotExist:
            msg = (f"Hang up response came from call-centre phone with no "
                   f"matching PusherSession. Perhaps the CCO wasn't in the "
                   f"call-centre app at the time?: {provided_id}")
            logger.debug(msg, extra={'extra_vars': self.temp_call,
                                     'request': self.request})
            # sentry_sdk.capture_message(msg)
        except PusherSession.MultipleObjectsReturned:
            pusher_sessions = PusherSession.objects.filter(provided_call_id=provided_id)
            msg = (f"Multiple PusherSessions found with the same provided id. "
                   f"Clearing their values, but we should not have got here: {provided_id}.")
            logger.debug(msg, extra={'temp_call': self.temp_call,
                                     'pusher_sessions': pusher_sessions,
                                     'request': self.request})
            sentry_sdk.capture_message(msg)

            for session in pusher_sessions:
                session.provided_call_id = None
                session.save(update_fields=['provided_call_id'])
        else:
            pusher_session.provided_call_id = None
            pusher_session.save(update_fields=['provided_call_id'])

        return ''

    def process_active_call_to_dequeue_number(self, caller_number,
                                              provided_id):
        """
        If call is active just create the dequeue response - we'll get
        another callback when the actual dequeue is executed so don't do
        anything with the call now.
        """
        try:
            pusher_session: PusherSession = PusherSession.objects.connected().get(
                call_center_phone__phone_number=caller_number)
        except PusherSession.DoesNotExist:
            return self.create_no_session_response()

        # Store the CCO's current call id for retrieval when we get
        # the dequeue response.
        call_center = pusher_session.get_priority_call_center()
        queue_name = None
        if call_center:
            queue_name = call_center.queue_name
        pusher_session.provided_call_id = provided_id
        pusher_session.save(update_fields=['provided_call_id'])
        return self.create_dequeue_response(queue_name=queue_name)

    def notify_pusher_new_call(self, call):
        self.notify_pusher(call, constants.NEW_CALL_EVENT_NAME)

    def notify_pusher_connect_call(self, call):
        self.notify_pusher(call, constants.CONNECTED_EVENT_NAME)

    def notify_pusher_hang_call(self, call):
        self.notify_pusher(call, constants.HANG_CALL_EVENT_NAME)

    def notify_pusher(self, call, what):
        instance = pusher.Pusher(app_id=client_setting('pusher_app_id'),
                                 key=client_setting('pusher_key'),
                                 secret=client_setting('pusher_secret'))
        serializer = SimpleCallSerializer(call)
        r = JSONRenderer().render(serializer.data).decode("utf-8")
        instance.trigger(constants.CC_CHANNEL_NAME, what, {'call': r})

    def _create_base_xml_response(self):
        """ Returns XML document and base 'Response' element. """
        doc = Document()
        base = doc.createElement('Response')
        doc.appendChild(base)
        return doc, base

    def create_queue_response(self):
        doc, base = self._create_base_xml_response()
        element = doc.createElement('Enqueue')
        base.appendChild(element)
        call_center: CallCenter = None
        if self.temp_call.customer:
            call_center = self.temp_call.customer.call_center
        base_url = client_setting('domain')
        hold_url = static(client_setting('hold_recording'))
        if hold_url:
            element.setAttribute('holdMusic', urljoin(base_url, hold_url))
        if call_center:
            element.setAttribute('name', call_center.queue_name)
        return doc.toxml()

    def create_dequeue_response(self, queue_name: str = None):
        doc, base = self._create_base_xml_response()
        element = doc.createElement('Dequeue')
        base.appendChild(element)
        element.setAttribute('phoneNumber', client_setting('voice_queue_number'))
        if queue_name:
            element.setAttribute('name', queue_name)
        return doc.toxml()

    def create_play_recording_response(self, recording_url):
        doc, base = self._create_base_xml_response()
        element = doc.createElement('Play')
        base_url = client_setting('domain')
        element.setAttribute('url', urljoin(base_url, recording_url))
        base.appendChild(element)
        return doc.toxml()

    def create_say_something_response(self, something_to_say):
        doc, base = self._create_base_xml_response()
        element = doc.createElement('Say')
        base.appendChild(element)
        element.setAttribute('voice', 'man')
        element.setAttribute('playBeep', 'false')
        textnode = doc.createTextNode(something_to_say)
        element.appendChild(textnode)
        return doc.toxml()

    def create_reject_response(self):
        doc, base = self._create_base_xml_response()
        element = doc.createElement('Reject')
        base.appendChild(element)
        return doc.toxml()

    def create_disallowed_customer_response(self):
        return self.create_play_recording_response(
            static(client_setting('inactive_recording'))
        )

    def create_empty_call_center_response(self):
        return self.create_play_recording_response(
            static(client_setting('closed_recording'))
        )

    def create_no_session_response(self):
        return self.create_say_something_response(
            constants.NO_SESSION_FOR_CCO_MESSAGE
        )

    def post(self, request, *args, **kwargs):
        self.handle_voice_options()
        resp = self.route_call()
        return HttpResponse(resp, content_type='application/xml')


class PusherAuthView(View):
    http_method_names = ('post', 'options',)

    def post(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseForbidden()

        latest_user_session = PusherSession.objects.filter(
            operator=self.request.user
        ).latest('created_on')
        # Check if we should allow the user - for debug allow him anyway
        if not settings.DEBUG:
            # User already has active pusher session?
            if latest_user_session.pusher_session_key:
                return HttpResponseForbidden()

            phone = latest_user_session.call_center_phone
            if (PusherSession.objects.connected()
                                     .filter(call_center_phone=phone)
                                     .exists()):
                return HttpResponseForbidden()

        socket_id = self.request.POST.get('socket_id')

        # Ok - set the session key for pusher
        latest_user_session.pusher_session_key = socket_id
        latest_user_session.save()

        channel_data = {
            'user_id': socket_id,
            'user_info': {
                'username': self.request.user.username,
                'phone': latest_user_session.call_center_phone.format_phone_number(),
            },
        }

        channel_name = self.request.POST.get('channel_name')
        p = pusher.Pusher(app_id=client_setting('pusher_app_id'),
                          key=client_setting('pusher_key'),
                          secret=client_setting('pusher_secret'))
        auth = p.authenticate(channel_name, socket_id, channel_data)

        return JsonResponse(auth)


class CallQueueView(View):
    http_method_names = ('get', 'options',)

    def get(self, request, *args, **kwargs):
        serializer = SimpleCallSerializer(Call.objects.queued(), many=True)
        r = JSONRenderer().render(serializer.data).decode("utf-8")
        return HttpResponse(r)


class ConnectedCallsView(View):
    http_method_names = ('get', 'options',)

    def get(self, request, *args, **kwargs):
        serializer = CallSerializer(Call.objects.connected(), many=True)
        r = JSONRenderer().render(serializer.data).decode("utf-8")
        return HttpResponse(r)

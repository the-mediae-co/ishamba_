import logging

from customers.constants import JOIN_METHODS
from . import directors  # this is needed for side-effects - director registration
from typing import Optional

from django.http import HttpRequest, HttpResponse
from phonenumber_field.phonenumber import PhoneNumber

from customers.models import Customer, get_or_create_customer_by_phone, CustomerSurvey
from interrogation.interface import Director


LOGGER = logging.getLogger(__name__)


class SessionManager:
    """SessionManager is responsible for the mechanics of each interrogation session:
     - at the start of the session, manager picks the director who bids the most, and installs him to run the
       interrogation
     - throughout the session, manager sends customer inputs to manager and gets back new questions to ask
     - manager remembers the last question asked so he can stitch multiple USSD sessions into a single
       interrogation session
     - single instance of SessionManager is responsible for a single interrogation session

    Instances of SessionManager have a lifecycle that spans multiple HTTP requests/responses, need to
    survive server restart, as well as function correctly in case of multiple backends serving requests.
    To ensure this, the instances must be pickle-able, since they might be serialized and deserialized
    between subsequent HTTP requests. Since SessionManager stores Director instance, this also means
    that directors must be pickleable.
    """

    director: Optional[Director] = None  # current director
    last_question: str = None  # last question requested by the current interrogator
    ussd_session_id: str = None  # current USSD session id
    all_text: Optional[str] = None
    finished: bool = False

    def get_director(self, customer: Customer, survey_title: str = '') -> Optional[Director]:
        """
        Get Director instance that will be responsible for directing the interrogation.
        The choice goes to the Director which makes the highest bid.
        """
        bids = [(dc.make_bid(customer, survey_title), dc) for dc in Director.registry]
        bids = [(bid, dc) for bid, dc in bids if bid > 0]
        if not bids:
            return None
        bids = sorted(bids, key=lambda pair: pair[0], reverse=1)
        _, dc = bids[0]
        return dc()

    def handler(self, request: HttpRequest, survey_title: str = '') -> HttpResponse:
        assert self.finished is False, 'Received request in completed session'
        qd = request.POST or request.GET
        ussd_session_id = qd.get("sessionId")
        text: Optional[str] = qd.get('text', None) or None   # we make sure empty string gets converted to None
        phone = PhoneNumber.from_string(qd.get('phoneNumber', ''))
        LOGGER.info(f'Got: {text} on session {ussd_session_id}')
        if not phone.is_valid():
            raise ValueError(f'Invalid phone number in USSD handler: {phone}')

        if self.ussd_session_id is not None and self.ussd_session_id != ussd_session_id:
            # we are stitching sessions, we'll replay the last question
            assert self.last_question is not None, 'last question not available while stitching USSD sessions'
            assert text is None, f'Unexpected input "{text}" received while stitching USSD sessions'
            # reset session and cumulative text received
            self.ussd_session_id = ussd_session_id
            self.all_text = None
            return HttpResponse(f'CON {self.last_question}')

        self.ussd_session_id = ussd_session_id
        if self.all_text is not None:
            assert text.startswith(self.all_text), f'Unexpected text received, expected {self.all_text}'
            # The rest of the text should start with *, but AT sometimes inserts an extra space. To be safe(r),
            # we'll ignore everything up to (and including) the next *
            ind = text.index('*', len(self.all_text))
            self.all_text, text = text, text[ind + 1:]
        else:
            self.all_text = text

        if text:
            # Skip AT's commands to show the rest of a long text prompt
            text = text.replace('98*', '')
            text = text.replace('00*', '')

        customer, created = get_or_create_customer_by_phone(phone, JOIN_METHODS.USSD)
        self.director = self.director or self.get_director(customer, survey_title)
        if not self.director:
            self.finished = True
            return HttpResponse(f'END Thank you for contacting iShamba. We have no questions for you at this time.')
        self.last_question = self.director.aq(customer, text)
        if self.last_question is not None and text is None:
            # this is start of interrogation, append the greeting
            self.last_question = f'{self.director.get_hello(customer)}{self.last_question}'
        if self.last_question is not None:
            return HttpResponse(f'CON {self.last_question}')
        # interrogation is done
        self.finished = True
        # AT does not like empty END response - we must greet the customer some way
        goodbye = self.director.get_goodbye(customer) or 'Goodbye.'
        return HttpResponse(f'END {goodbye}')

    def is_finished(self):
        return self.finished

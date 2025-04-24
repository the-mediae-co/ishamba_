from typing import Any, Optional, List, Type
from datetime import date

from customers.models import Customer


class StopInterrogation(Exception):
    def __init__(self, goodbye_message=None):
        self.goodbye_message = goodbye_message


class Interrogator:
    """Interrogator is responsible for asking question(s) and processing response(s) as needed to acquire
    one logical customer attribute, and for storing that attribute on the customer.
    By "logical attribute" we mean one logical thing, such as location, even if multiple questions
    need to be asked, and multiple fields might be used to store the answer.

    Instances of Interrogator subclasses have a lifecycle that spans multiple HTTP requests/responses, need to
    survive server restart, as well as function correctly in case of multiple backends serving requests.
    To ensure this, all subclasses must be pickle-able, since instances might be serialized and deserialized
    between subsequent requests.

    Each instance is tied to a single interrogation session of a single customer, and can store instance
    variables to maintain the state between requests.

    When storing acquired attributes on a customer, Interrogator should use
        customer.save(update_fields=...)
    variant in order to limit modifications to just the desired fields, in case the customer instance
    is cached and (somewhat) out of date.
    """

    @classmethod
    def is_needed(cls, customer: Customer) -> bool:
        """Returns true if attribute is currently unavailable (and interrogation would be helpful)."""
        raise NotImplementedError()

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        """Takes customer input (response to the previous question), processes it, and returns the next
        question to ask.

        This is the main method of this class, which does all the work. "aq" stands for answer-question.

        inp is None on the first invocation, before any questions were asked.

        return value being None indicates that attribute acquisition has been completed, and no
        further questions need to be asked.
        """

        raise NotImplementedError()

    def save(self, customer: Customer, value):
        """Called by aq to save the parsed data to the corresponding database field.
        """

        raise NotImplementedError()


class SurveyInterrogator:
    """SurveyInterrogator is responsible for asking question(s) and processing response(s) as needed to
    acquire survey responses.

    Instances of SurveyInterrogator subclasses have a lifecycle that spans multiple HTTP requests/responses, need to
    survive server restart, as well as function correctly in case of multiple backends serving requests.
    To ensure this, all subclasses must be pickle-able, since instances might be serialized and deserialized
    between subsequent requests.

    Each instance is tied to a single interrogation session of a single customer, and can store instance
    variables to maintain the state between requests.
    """
    question_key: str
    preferred_language: str

    def __init__(self, question_key: str, survey_title: str, preferred_language: str, details: Optional[Any]):
        raise NotImplementedError()

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        """Takes customer input (response to the previous question), processes it, and returns the next
        question to ask.

        This is the main method of this class, which does all the work. "aq" stands for answer-question.

        inp is None on the first invocation, before any questions were asked.

        return value being None indicates that attribute acquisition has been completed, and no
        further questions need to be asked.
        """

        raise NotImplementedError()

    def save(self, customer: Customer, value):
        """Called by aq to save the parsed data to the corresponding database field.
        """

        raise NotImplementedError()


class Director:
    """Director directs the interrogation by picking which questions to ask, in what order, and when
    to finish the interrogation.
    This is pure abstract class.
    """

    registry: list[Type['Director']] = []
    hidden: list[str]  # Questions whose responses are internal and not exportable

    @classmethod
    def make_bid(cls, customer: Customer, survey_title: str = '') -> float:
        """Make a bid to interrogate the customer. Zero means not interested. Highest bid wins."""
        raise NotImplementedError()

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        """Takes customer input (response to the previous question), processes it, and returns the next
        question to ask. "aq" stands for answer-question.

        inp is None on the first invocation, before any questions were asked.

        return value being None indicates that attribute acquisition has been completed, and no
        further questions need to be asked.
        """
        raise NotImplementedError()

    def get_hello(self, customer: Customer) -> str:
        raise NotImplementedError()

    def get_goodbye(self, customer: Customer) -> str:
        raise NotImplementedError()


def register_director(cls: Type[Director]):
    """Decorator for registering Director implementations with the USSD handler."""
    if cls not in Director.registry:
        Director.registry.append(cls)
    return cls

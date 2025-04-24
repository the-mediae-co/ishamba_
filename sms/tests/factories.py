import uuid

from django.utils import timezone

from factory.django import DjangoModelFactory
import factory.fuzzy
from gateways import gateways

from .. import models


class IncomingSMSFactory(DjangoModelFactory):
    class Meta:
        model = models.IncomingSMS

    sender = factory.SelfAttribute('customer.main_phone')
    recipient = '12345'
    customer = factory.SubFactory('customers.tests.factories.CustomerFactory')
    at = factory.LazyFunction(timezone.now)
    customer_created = True
    gateway_id = factory.fuzzy.FuzzyAttribute(lambda: str(uuid.uuid4()))
    gateway = gateways.AT


class OutgoingSMSFactory(DjangoModelFactory):
    class Meta:
        model = models.OutgoingSMS

    text = "This is a test"


class SMSResponseTemplateFactory(DjangoModelFactory):
    class Meta:
        model = models.SMSResponseTemplate

    name = 'A response template'
    text = 'Some text'

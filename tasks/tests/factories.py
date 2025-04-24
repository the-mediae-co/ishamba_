import factory
from factory.django import DjangoModelFactory
from django.contrib.contenttypes.models import ContentType

from customers.tests.factories import CustomerFactory
from sms.tests.factories import IncomingSMSFactory
from ..models import Task


class TaskFactory(DjangoModelFactory):

    class Meta:
        model = Task

    # customer = factory.SubFactory(CustomerFactory)
    customer = factory.SelfAttribute('source.customer')
    description = factory.Sequence(lambda n: 'Task description %d' % n)
    object_id = factory.SelfAttribute('source.id')
    content_type = factory.LazyAttribute(
        lambda o: ContentType.objects.get_for_model(o.source))
    source = factory.SubFactory(IncomingSMSFactory)
    last_editor_id = 1

import factory
from factory.django import DjangoModelFactory

from world.models import Border

from ..models import CallCenter


class CallCenterFactory(DjangoModelFactory):
    class Meta:
        model = CallCenter

    name = factory.Sequence(lambda n: f'Call Center {n}')
    description = factory.Faker('text')
    border = factory.LazyAttribute(lambda o: Border.objects.get(country='Kenya', level=0))


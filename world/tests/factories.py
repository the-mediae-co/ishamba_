import factory
from factory.django import DjangoModelFactory

from ..models import Border


class BorderFactory(DjangoModelFactory):
    class Meta:
        model = Border

    country = factory.Sequence(lambda n: f'Country {n}')
    level = factory.Faker('random_int', min=1, max=5)
    parent = None
    name = factory.Sequence(lambda n: f'Border {n}')
    name_en = factory.Faker('word')
    border = factory.Sequence(lambda n: f'Border Value {n}')

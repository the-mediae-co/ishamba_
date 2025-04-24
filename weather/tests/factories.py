import factory
from datetime import timedelta
from django.utils import timezone
from factory.django import DjangoModelFactory
from psycopg2.extras import DateRange

from customers.models import CustomerCategory
from world.models import Border
from ..models import CountyForecast


class CountyForecastFactory(DjangoModelFactory):
    class Meta:
        model = CountyForecast

    dates = factory.LazyAttribute(lambda o: DateRange(timezone.now().date(), (timezone.now() + timedelta(days=31)).date()))
    county = factory.LazyAttribute(lambda o: Border.objects.filter(country='Kenya', level=1).order_by('?').first())
    # premium_only = factory.Faker("boolean", chance_of_getting_true=50)
    premium_only = True
    text = factory.Sequence(lambda n: 'Forecast %d' % n)
    category = None

    @factory.post_generation
    def add_category(self, create, extracted, **kwargs):
        # Note that when called (post_generation), the county forecast object has been
        # created and the "self" passed in is the county forecast object, not the factory.
        if not create:
            return

        if extracted:
            category = extracted
            if isinstance(category, str):
                cat_obj = CustomerCategory.objects.create(name=category)
                self.category = cat_obj
            elif isinstance(category, CustomerCategory):
                self.category = category
            else:
                raise ValueError(f"Expected category str or CustomerCategory object, but got {category.__class__}")

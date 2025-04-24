from random import randint
from unittest import skip

from django.core.exceptions import ValidationError

import phonenumbers

from calls.tests.util import generate_phone_number
from core.test.cases import TestCase
from world.models import Border

from ..models import Customer
from .factories import CustomerFactory, CustomerPhoneFactory


class CustomerMethodTests(TestCase):

    @skip('This behavior has been turned off for now')
    def test_clean_invalid_location_and_county(self):
        county = Border.objects.filter(country='Kenya', level=1).order_by('?').first()
        location = '{"type":"Point","coordinates":[-1.2729360401038594,36.863250732421875]}'

        customer = Customer(county=county, location=location)

        with self.assertRaisesRegex(ValidationError, "The customer's location and county do not correspond with each other"):
            customer.clean()

    def generate_phone_number(self, prefix, length, max_iter=1000):
        """Generate random phone number for a given country code (prefix) and length,
        with digifarm +492 prefix handling special-cased.
        Gives up after max_iter iterations.
        """
        if prefix == 49:
            prefix = 492
            length -= 1
        lower = int('9' * (length - 1))
        upper = int('9' * length)
        tries = 0
        while (tries := tries + 1) < max_iter:
            phone_number = '{}{}{}'.format('+', prefix, randint(int(lower), int(upper)))
            return phone_number

    def test_main_phone_works(self):
        customer = CustomerFactory(has_no_phones=True)
        phone = CustomerPhoneFactory(number='+254722123456', is_main=False, customer=customer)
        df_number = generate_phone_number(prefix=phonenumbers.country_code_for_region('DE'), length=9)
        df_phone = CustomerPhoneFactory(number=df_number, is_main=True, customer=customer)
        # If no main number other than a fake digifarm german number, we expect None
        self.assertEqual(None, customer.main_phone)

        # If we try to create two main numbers, we expect a database constraint error
        with self.assertRaises(ValidationError):
            phone.is_main = True
            phone.save()

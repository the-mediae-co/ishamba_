import itertools
import datetime
import dateparser
from decimal import Decimal
from typing import List, Tuple, Optional, Type, Union

import mockito
import re

from django.contrib.gis.geos import Point
from django.http import HttpResponse
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.client import TenantClient

from core.constants import SEX_SPECIFIED
from core.test.cases import TestCase
from customers.constants import JOIN_METHODS

from interrogation import interrogators
from agri.models import COMMODITY_MAP_CACHE
from agri.tests.factories import CommodityFactory
from customers.models import Customer, CustomerPhone, CropHistory
from customers.tests.factories import CustomerFactory, CustomerPhoneFactory
from interrogation.interface import Interrogator, Director
from interrogation.directors import BaseDirector, RegistrationDirector, LetItRainDirector
from interrogation.interrogators import (FreeInputInterrogator, DateInterrogator, BirthdayInterrogator,
                                         LocationInterrogator, NameInterrogator, FarmOwnershipInterrogator,
                                         CropsInterrogator, LiveStockInterrogator, CropsConfirmer,
                                         GenderInterrogator, LetItRainDateFirstGuessInterrogator,
                                         LetItRainDateSecondGuessInterrogator, LetItRainDateThirdGuessInterrogator,
                                         FarmSizeInterrogator,
                                         CertifiedSeedsInterrogator, FertilizerInterrogator, CropsFailedInterrogator,
                                         CropsInsuranceInterrogator, ReceivesForecastsInterrogator,
                                         WeatherForcastFrequencyInterrogator, WeatherForcastSourceInterrogator,
                                         ExperiencedFloodsInterrogator, ExperiencedDroughtInterrogator,
                                         ExperiencedPestsInterrogator, ExperiencedDiseaseInterrogator)

from tasks.models import Task
from world.models import COUNTY_CACHE


class BaseInterrogatorTest(TestCase):

    interrogator_class: Type[Interrogator]

    def setUp(self) -> None:
        super().setUp()
        self.customer: Customer = CustomerFactory(location=None, has_no_tips=True)
        self.interrogator = self.interrogator_class()

    def helper(self, sequence: List[Tuple[str, Union[str, re.Pattern]]]):
        for inp, out_wanted in sequence:
            out = self.interrogator.aq(self.customer, inp)
            if isinstance(out_wanted, re.Pattern):
                self.assertTrue(out_wanted.search(out), f'Pattern "{out_wanted.pattern}" not found in "{out}"')
            else:
                self.assertEqual(out_wanted, out)
        self.customer.refresh_from_db()


class DateInterrogatorTests(BaseInterrogatorTest):

    interrogator_class = DateInterrogator

    def test_dashed_descriptive_date_input_updates_customer(self):
        sequence = [
            (None, DateInterrogator.question),
            ('11-Dec-2021', None)
        ]
        self.interrogator.customer_field = 'dob'
        self.helper(sequence)
        self.assertEqual(self.customer.dob, datetime.datetime(2021, 12, 11).date())

    def test_dotted_descriptive_date_input_updates_customer(self):
        sequence = [
            (None, DateInterrogator.question),
            ('11.Dec.2021', None)
        ]
        self.interrogator.customer_field = 'dob'
        self.helper(sequence)
        self.assertEqual(self.customer.dob, datetime.datetime(2021, 12, 11).date())

    def test_spaced_descriptive_date_input_updates_customer(self):
        sequence = [
            (None, DateInterrogator.question),
            ('11 Dec 2021', None)
        ]
        self.interrogator.customer_field = 'dob'
        self.helper(sequence)
        self.assertEqual(self.customer.dob, datetime.datetime(2021, 12, 11).date())

    def test_dashed_numerical_date_input_updates_customer(self):
        sequence = [
            (None, DateInterrogator.question),
            ('11-12-2021', None)
        ]
        self.interrogator.customer_field = 'dob'
        self.helper(sequence)
        self.assertEqual(self.customer.dob, datetime.datetime(2021, 12, 11).date())

    def test_dotted_numerical_date_input_updates_customer(self):
        sequence = [
            (None, DateInterrogator.question),
            ('11.12.2021', None)
        ]
        self.interrogator.customer_field = 'dob'
        self.helper(sequence)
        self.assertEqual(self.customer.dob, datetime.datetime(2021, 12, 11).date())

    def test_spaced_numerical_date_input_updates_customer(self):
        sequence = [
            (None, DateInterrogator.question),
            ('11 12 2021', None)
        ]
        self.interrogator.customer_field = 'dob'
        self.helper(sequence)
        self.assertEqual(self.customer.dob, datetime.datetime(2021, 12, 11).date())

    def test_year_only_date_input_repeats(self):
        sequence = [
            (None, DateInterrogator.question),
            ('2021', f'Please try again. ')
        ]
        self.interrogator.customer_field = 'dob'
        self.helper(sequence)
        self.assertEqual(None, self.customer.dob)

    def test_invalid_input_repeat_question_succeed_second_time(self):
        sequence = [
            (None, DateInterrogator.question),
            ('x', f'Please try again. '),
            ('11-Dec-2021', None)
        ]
        self.interrogator.customer_field = 'dob'
        self.helper(sequence)
        self.assertEqual(self.customer.dob, datetime.datetime(2021, 12, 11).date())


class BirthdayInterrogatorTests(BaseInterrogatorTest):

    interrogator_class = BirthdayInterrogator

    def test_dashed_descriptive_date_input_updates_customer(self):
        sequence = [
            (None, BirthdayInterrogator.question),
            ('11-Dec-2021', None)
        ]
        self.interrogator.customer_field = 'dob'
        self.helper(sequence)
        self.assertEqual(self.customer.dob, datetime.datetime(2021, 12, 11).date())

    def test_year_only_date_input_updates_customer(self):
        sequence = [
            (None, BirthdayInterrogator.question),
            ('2021', None)
        ]
        self.interrogator.customer_field = 'dob'
        self.helper(sequence)
        self.assertEqual(self.customer.dob, datetime.datetime(2021, 7, 1).date())

    def test_invalid_input_repeat_question_succeed_second_time(self):
        sequence = [
            (None, BirthdayInterrogator.question),
            ('x', f'Please try again. {BirthdayInterrogator.question}'),
            ('2021', None)
        ]
        self.interrogator.customer_field = 'dob'
        self.helper(sequence)
        self.assertEqual(self.customer.dob, datetime.datetime(2021, 7, 1).date())


class LocationInterrogatorTests(BaseInterrogatorTest):

    interrogator_class = LocationInterrogator

    def setUp(self) -> None:
        super().setUp()
        COUNTY_CACHE.clear()

    def test_school_not_matched(self):
        sequence = [
            (None, LocationInterrogator.WHAT_COUNTY),
            ('bringo', LocationInterrogator.WHAT_SCHOOL),
            ('Devonshire Elementary', re.compile(f'6. {LocationInterrogator.NONE_OF_THE_ABOVE}', re.I)),
            ('6', None)
        ]
        self.helper(sequence)
        self.assertIsNone(self.customer.location)
        self.assertEqual('bringo', self.customer.misc_data.county_name_raw)
        self.assertEqual('Baringo', self.customer.border1.name)
        self.assertEqual('Devonshire Elementary', self.customer.misc_data.school_name_raw)
        # make sure agent task was created to figure out the location
        self.assertEqual(1, Task.objects.count())
        task = Task.objects.all().first()
        self.assertEqual(task.source, self.customer)
        self.assertTrue('Devonshire Elementary' in task.description)
        self.assertTrue('bringo' in task.description)

    def test_school_matched_and_confirmed(self):
        sequence = [
            (None, LocationInterrogator.WHAT_COUNTY),
            ('bringo', LocationInterrogator.WHAT_SCHOOL),
            ('cheglet', re.compile('1. Chegilet, Elgeyo Marakwet', re.I)),
            ('1', None)
        ]
        self.helper(sequence)
        self.assertEqual(self.customer.location, Point(x=35.596590, y=0.830610, srid=4326))
        self.assertEqual('bringo', self.customer.misc_data.county_name_raw)
        self.assertEqual('Baringo', self.customer.border1.name)
        self.assertEqual('cheglet', self.customer.misc_data.school_name_raw)
        # no agent task created this time
        self.assertEqual(0, Task.objects.count())


class NameInterrogatorTests(BaseInterrogatorTest):

    interrogator_class = NameInterrogator

    def test_enter_name_customer_updated(self):
        sequence = [
            (None, NameInterrogator.question),
            ('John Doe', None)
        ]
        self.helper(sequence)
        self.assertEqual(self.customer.name, 'John Doe')

    def test_invalid_input_repeat_question_succeed_second_time(self):
        sequence = [
            (None, NameInterrogator.question),
            ('x', f'Please try again. {NameInterrogator.question}'),
            ('Sherlock Holmes', None)
        ]
        self.helper(sequence)
        self.assertEqual(self.customer.name, 'Sherlock Holmes')


class FarmOwnershipInterrogatorTests(BaseInterrogatorTest):

    interrogator_class = FarmOwnershipInterrogator

    def test_enter_yes_updated(self):
        sequence = [
            (None, 'Do you own your farm?\n1. Yes\n2. No'),
            ('1', None)
        ]
        self.helper(sequence)
        self.assertTrue(self.customer.owns_farm)

    def test_enter_no_updated(self):
        sequence = [
            (None, 'Do you own your farm?\n1. Yes\n2. No'),
            ('2', None)
        ]
        self.helper(sequence)
        self.assertFalse(self.customer.owns_farm)

    def test_enter_nothing_repeats(self):
        sequence = [
            (None, 'Do you own your farm?\n1. Yes\n2. No'),
            (None, 'Do you own your farm?\n1. Yes\n2. No')
        ]
        self.helper(sequence)
        self.assertIsNone(self.customer.owns_farm)


class CropsInterrogatorTests(BaseInterrogatorTest):

    interrogator_class = CropsInterrogator

    def setUp(self) -> None:
        super().setUp()
        self.beans = CommodityFactory(name='beans', crop=True)
        self.maize = CommodityFactory(name='corn', short_name='maize', crop=True)
        self.cows = CommodityFactory(name='Cows', seasonal_livestock=True)
        self.goats = CommodityFactory(name='goats', seasonal_livestock=True)
        COMMODITY_MAP_CACHE.clear()
        super().setUp()

    def test_entered_choices_are_recognized_and_customer_updated(self):
        inp = 'beens.maize notfound'
        sequence = [
            (None, CropsInterrogator.QUESTION),
            (inp, None)
        ]
        self.helper(sequence)
        self.assertEqual(self.customer.misc_data.crops_raw, inp)
        self.assertEqual({self.beans, self.maize}, set(self.customer.commodities.all()))
        # part of the input that was not matched
        self.assertEqual(self.customer.misc_data.crops_unmatched, len('notfound'))

    def test_none_entered_and_crops_removed(self):
        sequence = [
            (None, CropsInterrogator.QUESTION),
            ('"none&. ', None)
        ]
        self.customer.commodities.set([self.cows, self.beans])
        self.helper(sequence)
        self.assertEqual(list(self.customer.commodities.all()), [self.cows])

    def tearDown(self) -> None:
        COMMODITY_MAP_CACHE.clear()
        super().tearDown()


class LivestockInterrogatorTests(BaseInterrogatorTest):

    interrogator_class = LiveStockInterrogator

    def setUp(self) -> None:
        super().setUp()
        self.beans = CommodityFactory(name='beans', crop=True)
        self.maize = CommodityFactory(name='corn', short_name='maize', crop=True)
        self.cows = CommodityFactory(name='Cows', seasonal_livestock=True)
        self.goats = CommodityFactory(name='goats', seasonal_livestock=True)
        COMMODITY_MAP_CACHE.clear()
        super().setUp()

    def test_none_entered_and_livestock_removed(self):
        sequence = [
            (None, LiveStockInterrogator.QUESTION),
            ('none', None)
        ]
        self.customer.commodities.set([self.cows, self.beans])
        self.helper(sequence)
        self.assertEqual(list(self.customer.commodities.all()), [self.beans])


class CropsConfirmerTests(BaseInterrogatorTest):

    interrogator_class = CropsConfirmer

    def setUp(self) -> None:
        super().setUp()
        self.beans = CommodityFactory(name='Beans', crop=True, season_length_days=60)
        self.maize = CommodityFactory(name='corn', short_name='maize', crop=True, season_length_days=60)
        self.potatoes = CommodityFactory(name='irish potatoes', crop=True, season_length_days=60)
        self.olives = CommodityFactory(name='olive trees', crop=True)
        COMMODITY_MAP_CACHE.clear()
        super().setUp()

    def test_add_crops_starting_with_none(self):
        sequence = [
            (None, re.compile('any crops.*2. add crops', re.I | re.DOTALL)),
            ('2', CropsConfirmer.EnterCropState.Q),
            ('beans', re.compile('1. Beans')),
            ('1', re.compile(CropsConfirmer.ConfirmCropsState.PREAMBLE2[:10]))
        ]
        self.helper(sequence)
        self.assertEqual([self.beans], list(self.customer.commodities.all()))

    def test_confirm_crops_and_add_planting_dates(self):
        # we should only be asked about planting date for the beans
        self.customer.commodities.add(self.beans, self.olives)
        sequence = [
            (None, re.compile(f'1. {CropsConfirmer.ConfirmCropsState.CORRECT}')),
            ('1.', re.compile('planting schedule.*planting date for your beans', re.I | re.DOTALL)),
            ('15/03/2021', None)
        ]

        def patched_now():
            return datetime.datetime(2021, 3, 15, 0, 0, 0)

        with mockito.patch(interrogators.now, patched_now):
            self.helper(sequence)
        crop_history: CropHistory = CropHistory.objects.get(customer=self.customer)
        self.assertEqual(datetime.date(2021, 3, 15), crop_history.date_planted)

    def test_confirm_crops_with_invalid_planting_date(self):
        # we should only be asked about planting date for the beans
        self.customer.commodities.add(self.beans, self.olives)
        sequence = [
            (None, re.compile(f'1. {CropsConfirmer.ConfirmCropsState.CORRECT}')),
            ('1.', re.compile('planting schedule.*planting date for your beans', re.I | re.DOTALL)),
            ('15/03/1971', re.compile('.*planting date for your beans', re.I | re.DOTALL)),
            ('15/03/2021', None),
        ]
        with mockito.patch(interrogators.now, lambda: datetime.datetime(2021, 3, 10)):
            self.helper(sequence)
        crop_history: CropHistory = CropHistory.objects.get(customer=self.customer)
        self.assertEqual(datetime.date(2021, 3, 15), crop_history.date_planted)

    def test_skip_asking_for_planting_date_when_recent_history_present(self):
        self.customer.commodities.add(self.beans, self.maize)
        year = timezone.now().year
        # ancient crop history for maize
        CropHistory(customer=self.customer, commodity=self.maize, date_planted=datetime.date(1980, 1, 1)).save()
        # recent crop history for beans
        CropHistory(customer=self.customer, commodity=self.beans, date_planted=datetime.date(year, 2, 15)).save()
        # we should only get asked about maize
        sequence = [
            (None, re.compile(f'1. {CropsConfirmer.ConfirmCropsState.CORRECT}')),
            ('1.', re.compile('planting schedule.*planting date for your corn', re.I | re.DOTALL)),
            ('02.03', None)
        ]
        with mockito.patch(interrogators.now, lambda: datetime.datetime(year, 3, 10)):
            self.helper(sequence)
        crop_history: CropHistory = CropHistory.objects.filter(
            customer=self.customer, commodity=self.maize).order_by('-date_planted').first()
        expected_date = datetime.date(year, 3, 2)
        self.assertEqual(expected_date, crop_history.date_planted)

    def test_remove_crops_all_gone(self):
        self.customer.commodities.add(self.beans, self.maize)
        sequence = [
            (None, re.compile(f'3. {CropsConfirmer.ConfirmCropsState.REMOVE}')),
            ('3', re.compile(f'{CropsConfirmer.RemoveCropState.SELECT}')),
            ('2', re.compile(f'3. {CropsConfirmer.ConfirmCropsState.REMOVE}')),
            ('3', re.compile(f'{CropsConfirmer.RemoveCropState.SELECT}')),
            ('1', re.compile('any crops')),
            # option 3 - delete is not longer available, so just goes back to same screen
            ('3', re.compile('any crops'))
        ]
        self.helper(sequence)
        self.assertEqual(0, self.customer.commodities.all().count())


class TestInterrogator(Interrogator):
    Q1 = 'What is your name?'
    Q2 = 'Are you sure that is your name?'
    asked_q2 = False
    name: str

    @classmethod
    def is_needed(cls, customer: Customer) -> bool:
        return customer.name == ''

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.Q1
        elif self.asked_q2 is False:
            self.asked_q2 = True
            assert inp != ''
            self.name = inp
            return self.Q2
        else:
            assert inp != ''
            customer.name = self.name
            customer.save(update_fields=['name'])
            return None


class TestInterrogator2(FreeInputInterrogator):
    question = 'What is your village name?'
    customer_field = 'village'


class DirectorHelper(BaseDirector):
    interrogators = [TestInterrogator]
    bid = 1


class DirectorHelper2(BaseDirector):
    interrogators = [NameInterrogator, TestInterrogator2]
    hello = 'Hello there\n'
    goodbye = 'Stay well'
    bid = 2


# class DirectorHelperLIR(BaseDirector):
#     """Let It Rain director helper"""
#     interrogators: List[Type[Interrogator]] = [
#         LocationInterrogator,
#         GenderInterrogator,
#         BirthdayInterrogator,
#         NameInterrogator,
#         LetItRainDateFirstGuessInterrogator,  # Let the customer enter one guess after personal details are collected
#         FarmOwnershipInterrogator,
#         FarmSizeInterrogator,
#         LiveStockInterrogator,
#         CropsInterrogator,
#         CropsConfirmer,
#         CertifiedSeedsInterrogator,
#         FertilizerInterrogator,
#         LetItRainDateSecondGuessInterrogator,  # Let the customer enter one guess after farm details are collected
#         CropsFailedInterrogator,
#         CropsInsuranceInterrogator,
#         ReceivesForecastsInterrogator,
#         WeatherForcastFrequencyInterrogator,
#         WeatherForcastSourceInterrogator,
#         ExperiencedFloodsInterrogator,
#         ExperiencedDroughtInterrogator,
#         ExperiencedPestsInterrogator,
#         ExperiencedDiseaseInterrogator,
#         LetItRainDateThirdGuessInterrogator  # Let the customer enter one guess after climate impact details are collected
#     ]
#     hello = 'Hello there\n'
#     goodbye = 'Stay well'
#     bid = 3


class SessionTestsBase(TestCase):
    """Base class for creating tests that exercise an entire USSD session. The class plays a role
    of AT USSD server which is communicating with ishamba USSD handler on behalf of a user.
    The class keeps track of what text has been already sent, and correctly delimits the text with "*".
    """
    phone_number = '+254741210529'
    all_text: Optional[str]
    current_session_id: str = None

    def setUp(self) -> None:
        super().setUp()
        self.client = TenantClient(self.tenant)
        self.all_text = ''
        self.cycler = itertools.cycle([' ', ''])

    def send(self, text: str, session_id='abc') -> Tuple[bool, str]:
        """Make USSD request (playing the role of phone) and return tuple (continue, response_text)"""
        if self.current_session_id != session_id:
            self.all_text = None
        self.current_session_id = session_id
        # simulate evil AT behavior where an extra space is sometimes added to daze and confuse the enemy
        maybe_extra_space = next(self.cycler)
        self.all_text = f'{self.all_text}{maybe_extra_space}*{text}' if self.all_text else text
        with override_settings(IP_AUTHORIZATION=False):
            resp: HttpResponse = self.client.post(
                reverse('interrogation:interrogation'),
                data={'sessionId': session_id, 'text': self.all_text, 'phoneNumber': self.phone_number}
            )
        content = resp.content.decode()
        self.assertTrue(content.startswith('CON ') or content.startswith('END '))
        return content.startswith('CON '), content[4:]


class SessionTests1(SessionTestsBase):
    name = 'Farmer Farmerkovic'

    def setUp(self) -> None:
        super().setUp()
        self.saved_registry, Director.registry = Director.registry, [DirectorHelper]

    def tearDown(self) -> None:
        Director.registry = self.saved_registry
        super().tearDown()

    def testNewCustomerCompletesSession(self):
        cont, q = self.send('')
        self.assertTrue(cont, "Expected session to continue")
        self.assertEqual(q, TestInterrogator.Q1)
        cont, q = self.send(self.name)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(q, TestInterrogator.Q2)
        cont, _ = self.send('Y')
        self.assertFalse(cont, 'Expected session to finish')
        self.assertEqual(1, Customer.objects.count())
        customer = Customer.objects.all().first()
        self.assertEqual(customer.main_phone, self.phone_number)
        self.assertEqual(customer.name, self.name)
        self.assertEqual('Kenya', customer.border0.name)

    def testNewCustomerStitchedSessionCompleted(self):
        cont, q = self.send('', session_id='X')
        self.assertTrue(cont, "Expected session to continue")
        self.assertEqual(q, TestInterrogator.Q1)
        cont, q = self.send(self.name, session_id='X')
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(q, TestInterrogator.Q2)
        # now switch to a new session
        cont, q = self.send('', session_id='Y')
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(q, TestInterrogator.Q2)  # last question should be repeated
        cont, _ = self.send('Y', session_id='Y')
        self.assertFalse(cont, 'Expected session to finish')
        self.assertEqual(1, Customer.objects.count())
        customer = Customer.objects.all().first()
        self.assertEqual(customer.main_phone, self.phone_number)
        self.assertEqual(customer.name, self.name)
        self.assertEqual('Kenya', customer.border0.name)

    def testExistingCustomerNoNameSessionCompletes(self):
        customer: Customer = CustomerFactory(name='', phones__number=self.phone_number)
        self.testNewCustomerCompletesSession()
        customer.refresh_from_db()
        self.assertEqual(self.name, customer.name)
        self.assertEqual('factory', customer.join_method)  # The join_method of existing customers should not be modified
        self.assertEqual('Kenya', customer.border0.name)

    def testExistingCustomerHasNameSessionEndsImmediately(self):
        customer: Customer = CustomerFactory(name=self.name, phones__number=self.phone_number)
        cont, _ = self.send('')
        self.assertFalse(cont, 'Expected session to finish')


class SessionTests2(SessionTestsBase):
    name = 'Farmer Farmerkovic'
    village_name = 'Water Tower'

    def setUp(self) -> None:
        super().setUp()
        self.saved_registry, Director.registry = Director.registry, [DirectorHelper, DirectorHelper2]

    def tearDown(self) -> None:
        Director.registry = self.saved_registry
        super().tearDown()

    def testNewCustomerCompletesSessionWithGreetingAndGoodBye(self):
        cont, q = self.send('')
        self.assertTrue(cont, "Expected session to continue")
        self.assertEqual(q, f'{DirectorHelper2.hello}{NameInterrogator.question}')
        cont, q = self.send(self.name)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(q, TestInterrogator2.question)
        cont, q = self.send(self.village_name)
        self.assertFalse(cont, 'Expected session to finish')
        self.assertEqual(q, DirectorHelper2.goodbye)
        self.assertEqual(1, Customer.objects.count())
        customer = Customer.objects.all().first()
        self.assertEqual(customer.main_phone, self.phone_number)
        self.assertEqual(customer.name, self.name)
        self.assertEqual(customer.village, self.village_name)
        self.assertEqual(JOIN_METHODS.USSD, customer.join_method)
        self.assertEqual('Kenya', customer.border0.name)


class SessionTestsLIR(SessionTestsBase):
    name = 'Farmer Farmerkovic'
    location_county = 'Nairobi'
    location_school = 'Nairobi Primary'
    location_school_confirm = '1'
    gender = '1'
    birthday = '1978'
    first_guess = '31-1-2022'
    owns_farm = '1'
    farm_size = '2'
    livestock = 'cows, chickens'
    crops = 'maize, cassava'
    crops_confirm = '1'
    certified_seeds = '1'
    fertilizer = '3'
    second_guess = '29-1-2022'
    crops_failed = '1'
    crops_insurance = '2'
    receives_forecasts = '1'
    weather_frequency = '2'
    weather_source = '3'
    experienced_floods = '1'
    experienced_droughts = '1'
    experienced_pests = '1'
    experienced_diseases = '1'
    third_guess = '7-2-2022'

    def setUp(self) -> None:
        super().setUp()
        self.saved_registry, Director.registry = Director.registry, [LetItRainDirector]
        l1 = CommodityFactory(seasonal_livestock=True, name='Chickens')
        l2 = CommodityFactory(seasonal_livestock=True, name='Cows')
        c1 = CommodityFactory(crop=True, name='Maize')
        c2 = CommodityFactory(crop=True, name='Cassava')
        COMMODITY_MAP_CACHE.clear()

    def tearDown(self) -> None:
        Director.registry = self.saved_registry
        # Commodity.objects.all().delete()
        super().tearDown()

    def testNewCustomerCompletesSessionWithGreetingAndGoodBye(self):
        cont, q = self.send('')
        self.assertTrue(cont, "Expected session to continue")
        # Fake that this is an existing registered customer, so a welcome SMS won't be sent.
        customer = Customer.objects.first()
        customer.is_registered = True
        customer.save()
        # Ask a series of questions about the customer's location
        self.assertEqual(f'{LetItRainDirector.hello}{LocationInterrogator.WHAT_COUNTY}', q)
        cont, q = self.send(self.location_county)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(LocationInterrogator.WHAT_SCHOOL, q)
        cont, q = self.send(self.location_school)
        self.assertTrue(cont, 'Expected session to continue')
        cont, q = self.send(self.location_school_confirm)
        # Ask gender
        self.assertTrue(cont, 'Expected session to continue')
        menu_str = '\n'.join([f'{str(i + 1)}. {c[1]}' for i, c in enumerate(SEX_SPECIFIED.choices)])
        self.assertEqual(f'{GenderInterrogator.preamble}{menu_str}', q)
        cont, q = self.send(self.gender)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(BirthdayInterrogator.question, q)
        cont, q = self.send(self.birthday)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(NameInterrogator.question, q)
        cont, q = self.send(self.name)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(LetItRainDateFirstGuessInterrogator.question, q)
        cont, q = self.send(self.first_guess)
        self.assertTrue(cont, 'Expected session to finish')
        self.assertEqual(f'{FarmOwnershipInterrogator.preamble}1. Yes\n2. No', q)
        cont, q = self.send(self.owns_farm)
        self.assertTrue(cont, 'Expected session to continue')
        menu_str = '\n'.join([f'{str(i + 1)}. {c[0]}' for i, c in enumerate(FarmSizeInterrogator.menu_items)])
        self.assertEqual(f'{FarmSizeInterrogator.preamble}{menu_str}', q)
        cont, q = self.send(self.farm_size)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(f'{LiveStockInterrogator.QUESTION}', q)
        cont, q = self.send(self.livestock)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(f'{CropsInterrogator.QUESTION}', q)
        cont, q = self.send(self.crops)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(f"We think you grow these crops: Cassava, Maize\n1. That's correct\n2. Add crops\n3. Remove crops", q)
        cont, q = self.send(self.crops_confirm)
        self.assertTrue(cont, 'Expected session to continue')
        menu_str = '\n'.join([f'{str(i + 1)}. {c[0]}' for i, c in enumerate(CertifiedSeedsInterrogator.menu_items)])
        self.assertEqual(f'{CertifiedSeedsInterrogator.preamble}{menu_str}', q)
        cont, q = self.send(self.certified_seeds)
        menu_str = '\n'.join([f'{str(i + 1)}. {c[0]}' for i, c in enumerate(FertilizerInterrogator.menu_items)])
        self.assertEqual(f'{FertilizerInterrogator.preamble}{menu_str}', q)
        cont, q = self.send(self.fertilizer)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(LetItRainDateSecondGuessInterrogator.question, q)
        cont, q = self.send(self.second_guess)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(f'{CropsFailedInterrogator.preamble}1. Yes\n2. No', q)
        cont, q = self.send(self.crops_failed)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(f'{CropsInsuranceInterrogator.preamble}1. Yes\n2. No', q)
        cont, q = self.send(self.crops_insurance)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(f'{ReceivesForecastsInterrogator.preamble}1. Yes\n2. No', q)
        cont, q = self.send(self.receives_forecasts)
        self.assertTrue(cont, 'Expected session to continue')
        menu_str = '\n'.join([f'{str(i + 1)}. {c[0]}' for i, c in enumerate(WeatherForcastFrequencyInterrogator.menu_items)])
        self.assertEqual(f'{WeatherForcastFrequencyInterrogator.preamble}{menu_str}', q)
        cont, q = self.send(self.weather_frequency)
        self.assertTrue(cont, 'Expected session to continue')
        menu_str = '\n'.join([f'{str(i + 1)}. {c[0]}' for i, c in enumerate(WeatherForcastSourceInterrogator.menu_items)])
        self.assertEqual(f'{WeatherForcastSourceInterrogator.preamble}{menu_str}', q)
        cont, q = self.send(self.weather_source)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(f'{ExperiencedFloodsInterrogator.preamble}1. Yes\n2. No', q)
        cont, q = self.send(self.experienced_floods)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(f'{ExperiencedDroughtInterrogator.preamble}1. Yes\n2. No', q)
        cont, q = self.send(self.experienced_droughts)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(f'{ExperiencedPestsInterrogator.preamble}1. Yes\n2. No', q)
        cont, q = self.send(self.experienced_pests)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(f'{ExperiencedDiseaseInterrogator.preamble}1. Yes\n2. No', q)
        cont, q = self.send(self.experienced_diseases)
        self.assertTrue(cont, 'Expected session to continue')
        self.assertEqual(LetItRainDateThirdGuessInterrogator.question, q)
        cont, q = self.send(self.third_guess)

        self.assertEqual(LetItRainDirector.goodbye, q)
        self.assertEqual(1, Customer.objects.count())
        customer.refresh_from_db()

        self.assertEqual(self.phone_number, customer.main_phone)
        self.assertEqual(customer.join_method, JOIN_METHODS.USSD)

        letitrain_data = customer.get_or_create_letitrain_data()

        self.assertEqual('ussd', letitrain_data.data_source)

        self.assertEqual('Kenya', customer.border0.name)
        self.assertEqual(self.location_county, customer.border1.name)
        self.assertEqual('Dagoretti North', customer.border2.name)
        self.assertEqual('Kilimani', customer.border3.name)
        self.assertEqual('f', customer.sex)
        self.assertEqual(datetime.datetime(int(self.birthday), 7, 1).date(), customer.dob)
        parsed_date = dateparser.parse(self.first_guess.replace('.', '-'), settings={
            'DATE_ORDER': 'DMY',
            'STRICT_PARSING': True,
        }).date()
        self.assertEqual(parsed_date, letitrain_data.guesses[0])

        self.assertTrue(customer.owns_farm)
        self.assertEqual('1.50', customer.farm_size)
        livestock = customer.commodities.filter(commodity_type='livestock')
        self.assertEqual(2, livestock.count())
        for l in livestock:
            self.assertIn(l.name, ['Cows', 'Chickens'], 'Unknown livestock')

        crops = customer.commodities.filter(commodity_type='crop')
        self.assertEqual(2, crops.count())
        for c in crops:
            self.assertIn(c.name, ['Maize', 'Cassava'], 'Unknown livestock')

        self.assertTrue(letitrain_data.uses_certified_seed)
        self.assertEqual('both', letitrain_data.fertilizer_type)
        parsed_date = dateparser.parse(self.second_guess.replace('.', '-'), settings={
            'DATE_ORDER': 'DMY',
            'STRICT_PARSING': True,
        }).date()
        self.assertEqual(parsed_date, letitrain_data.guesses[1])

        self.assertTrue(letitrain_data.crops_have_failed)
        self.assertFalse(letitrain_data.has_crop_insurance)
        self.assertTrue(letitrain_data.receives_weather_forecasts)
        self.assertEqual(3, letitrain_data.forcast_frequency_days)
        self.assertEqual('other', letitrain_data.weather_source)
        self.assertTrue(letitrain_data.has_experienced_floods)
        self.assertTrue(letitrain_data.has_experienced_droughts)
        self.assertTrue(letitrain_data.has_experienced_pests)
        self.assertTrue(letitrain_data.has_experienced_diseases)
        parsed_date = dateparser.parse(self.third_guess.replace('.', '-'), settings={
            'DATE_ORDER': 'DMY',
            'STRICT_PARSING': True,
        }).date()
        self.assertEqual(parsed_date, letitrain_data.guesses[2])


class RegistrationSessionTests(SessionTestsBase):
    customer: Customer

    def setUp(self) -> None:
        super().setUp()
        self.saved_registry, Director.registry = Director.registry, [RegistrationDirector]

    def tearDown(self) -> None:
        Director.registry = self.saved_registry
        super().tearDown()

    def testUnregisteredCustomerWithNameAndLocationGetsRegistered(self):
        customer: Customer = CustomerFactory(name='blah', commodities=[], unregistered=True, has_no_phones=True)
        phone: CustomerPhone = CustomerPhoneFactory(number=self.phone_number, is_main=True, customer=customer)
        self.assertIsNotNone(customer.location)
        self.assertTrue(customer.name != '')

        with mockito.patch(Customer.send_welcome_sms, lambda: None):
            with self.captureOnCommitCallbacks(execute=True):
                cont, _ = self.send('')
            mockito.verify(Customer).send_welcome_sms()

        customer.refresh_from_db()
        self.assertTrue(customer.is_registered)

    def testRegisteredCustomerWithNameAndLocationNoRegistration(self):
        customer: Customer = CustomerFactory(name='blah', commodities=[], has_no_phones=True)
        phone: CustomerPhone = CustomerPhoneFactory(number=self.phone_number, is_main=True, customer=customer)
        self.assertIsNotNone(customer.location)
        self.assertTrue(customer.name != '')

        with mockito.patch(Customer.send_welcome_sms, lambda: None):
            with self.captureOnCommitCallbacks(execute=True):
                cont, _ = self.send('')
            mockito.verify(Customer, times=0).send_welcome_sms()


class TestIPAuthorization(TestCase):
    def testRequestGetsRejected(self):
        client = TenantClient(self.tenant)
        resp: HttpResponse = client.post(
            reverse('interrogation:interrogation'),
            data={'sessionId': '123', 'text': '', 'phoneNumber': '+254741210529'}
        )
        self.assertEqual(403, resp.status_code)

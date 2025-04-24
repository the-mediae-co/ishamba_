import logging
import re
from collections import namedtuple
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.gis.geos import Point
from django.db.models import Count
from django.utils import timezone

import dateparser
from fuzzywuzzy import process as fuzz_process

from agri.models import Commodity, get_commodity_map
from core.constants import FARM_SIZES_SPECIFIED, LANGUAGES, SEX_SPECIFIED
from customers.models import (CropHistory, Customer, CustomerLetItRainData,
                              CustomerSurvey)
from interrogation import fuzzy_matching
from interrogation.interface import (Interrogator, StopInterrogation,
                                     SurveyInterrogator)
from tasks.models import Task, TaskUpdate
from world import school_matching
from world.models import get_county_names_and_ids
from world.utils import get_border_for_location

LOGGER = logging.getLogger(__name__)


MenuItem = Tuple[str, object]
MenuItems = List[MenuItem]


class FreeInputInterrogator(Interrogator):
    question: str = ''
    customer_field: str = None
    transformer = str.strip
    min_length = 2

    @classmethod
    def is_needed(cls, customer: Customer) -> bool:
        val = getattr(customer, cls.customer_field)
        return val is None or val == ''

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.question
        if len(inp) < self.min_length:
            return f'Please try again. {self.question}'

        transformer = self.__class__.transformer  # needed to avoid interpreting this as method
        val = transformer(inp) if callable(transformer) else inp
        self.save(customer, val)
        return None

    def save(self, customer: Customer, val):
        setattr(customer, self.customer_field, val)
        customer.save(update_fields=[self.customer_field])


class DateInterrogator(FreeInputInterrogator):
    min_length = 4

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.question
        if len(inp) < self.min_length:
            return f'Please try again. {self.question}'

        transformer = self.__class__.transformer  # needed to avoid interpreting this as method
        val = transformer(inp) if callable(transformer) else inp
        imported_date = dateparser.parse(val.replace('.', '-'),
                                         settings={
                                             'DATE_ORDER': 'DMY',
                                             'STRICT_PARSING': True,
                                         })
        if imported_date is None:
            return f'Please try again. {self.question}'
        self.save(customer, imported_date)
        return None

    def save(self, customer: Customer, value):
        setattr(customer, self.customer_field, value)
        customer.save(update_fields=[self.customer_field])


class LetItRainDateInterrogator(DateInterrogator):
    min_length = 4
    letitrain_field = ''

    def save(self, customer: Customer, value):
        letitrain_data = customer.get_or_create_letitrain_data()
        setattr(letitrain_data, self.letitrain_field, value)
        letitrain_data.save(update_fields=[self.letitrain_field])


def get_menu_text(preamble: str, menu_items: MenuItems):
    return preamble + '\n'.join(
        f'{i}. {t[0]}' for i, t in enumerate(menu_items, 1)
    )


def get_menu_item(inp, menu_items: MenuItems) -> MenuItem:
    """Attempts to parse user input as menu selection, and returns selected menu item.
    Raise ValueError in case of invalid user input.
    """
    inp = inp.strip()
    if inp.endswith('.'):
        inp = inp[:-1]
    item_number = int(inp)
    try:
        return menu_items[item_number - 1]
    except IndexError:
        raise ValueError(inp)


class MenuInterrogator(Interrogator):
    # list of tuples (menu item, value to save into customer)
    menu_items: List[Tuple[str, object]] = None
    customer_field: str = None
    preamble: str = ''

    @classmethod
    def is_needed(cls, customer: Customer) -> bool:
        val = getattr(customer, cls.customer_field)
        return val is None or val == ''

    def get_menu_text(self, preamble=None):
        if preamble is None:
            preamble = self.preamble
        return get_menu_text(preamble, self.menu_items)

    def get_menu_item(self, inp) -> Tuple[str, object]:
        """Attempts to parse user input as menu selection, and returns selected menu item.
        Raise ValueError in case of invalid user input.
        """
        return get_menu_item(inp, self.menu_items)

    def save(self, customer: Customer, value):
        """Override this to customize saving the selected value into customer"""
        setattr(customer, self.customer_field, value)
        customer.save(update_fields=[self.customer_field])

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.get_menu_text()
        try:
            item = self.get_menu_item(inp)
        except ValueError:
            LOGGER.error(f'Invalid user input: {inp}')
            # try asking the same question again
            return self.get_menu_text()
        self.save(customer, item[1])


class LetItRainMenuInterrogator(MenuInterrogator):
    """
    A MenuInterrogator that stores the resulting values in the
    CustomerLetItRainData table instead of the customer record.
    """
    letitrain_field: str = None

    @classmethod
    def is_needed(cls, customer: Customer) -> bool:
        letitrain_data = customer.get_or_create_letitrain_data()
        val = getattr(letitrain_data, cls.letitrain_field)
        return val is None or val == ''

    def save(self, customer: Customer, value):
        """Override this to customize saving the selected value into letitrain_data"""
        letitrain_data = customer.get_or_create_letitrain_data()
        setattr(letitrain_data, self.letitrain_field, value)
        letitrain_data.save(update_fields=[self.letitrain_field])


class SurveyMenuInterrogator(SurveyInterrogator):
    # list of tuples (menu item, value to save into survey json)
    menu_items: List[Tuple[str, object]] = None
    question_name: str = None
    preamble: str = ''
    survey_title: str = ''

    def __init__(self, question_key: str, survey_title: str, preferred_language: str, details: dict):
        self.question_key = question_key
        self.preferred_language = preferred_language
        self.survey_title = survey_title
        if preferred_language == LANGUAGES.KISWAHILI.value:
            self.preamble = details.get('preamble_sw', details.get('preamble_en', details.get('preamble', '')))
            self.menu_items = details.get('menu_items_sw', details.get('menu_items_en', details.get('menu_items', [])))
        else:
            self.preamble = details.get('preamble_en', details.get('preamble', ''))
            self.menu_items = details.get('menu_items_en', details.get('menu_items', []))

    def get_menu_text(self, preamble=None):
        if preamble is None:
            preamble = self.preamble
        return get_menu_text(preamble, self.menu_items)

    def get_menu_item(self, inp) -> Tuple[str, object]:
        """Attempts to parse user input as menu selection, and returns selected menu item.
        Raise ValueError in case of invalid user input.
        """
        return get_menu_item(inp, self.menu_items)

    def save(self, customer: Customer, value):
        """Override this to customize saving the selected value into customer"""
        cs, created = CustomerSurvey.objects.get_or_create(
            customer_id=customer.id,
            survey_title=self.survey_title
        )
        cs.responses[self.question_key] = value
        cs.save(update_fields=['responses'])

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.get_menu_text()
        try:
            item = self.get_menu_item(inp)
        except ValueError:
            LOGGER.error(f'Invalid user input: {inp}')
            # try asking the same question again
            return self.get_menu_text()
        self.save(customer, item[1])


class SurveyGenderInterrogator(SurveyMenuInterrogator):

    def get_gender_counts(self):
        """
        Return the count of male and female respondents who have completed the survey.
        """
        return {i['responses__Sex']: i['count'] for i in
                CustomerSurvey.objects.filter(survey_title=self.survey_title,
                                              finished_at__isnull=False,
                                              responses__Sex__isnull=False).values(
                    'responses__Sex').annotate(count=Count('id'))}

    def check_gender_limit(self, gender):
        """
        Check if the number of respondents for the given gender has reached the limit.
        """
        gender_counts = self.get_gender_counts()

        if gender == 'm':
            limit = settings.CIAT_DIET_QUALITY_SURVEY_MAX_RESPONDENTS_PER_GENDER_MALE
        elif gender == 'f':
            limit = settings.CIAT_DIET_QUALITY_SURVEY_MAX_RESPONDENTS_PER_GENDER_FEMALE
        else:
            return False  # Return False if gender is not 'm' or 'f'

        return gender_counts.get(gender, 0) < limit

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.get_menu_text()
        try:
            item = self.get_menu_item(inp)
        except ValueError:
            LOGGER.error(f'Invalid user input: {inp}')
            # try asking the same question again
            return self.get_menu_text()

        if not self.check_gender_limit(item[1]):
            raise StopInterrogation(
                "Sorry, this survey has reached the maximum number of respondents of your gender. Thank you for your interest.")

        self.save(customer, item[1])


class SurveyFreeInputInterrogator(SurveyMenuInterrogator):
    def __init__(self, question_key: str, survey_title: str, preferred_language: str, details: dict):
        super().__init__(question_key, survey_title, preferred_language, details)
        self.prompt = self.get_prompt(details, preferred_language)

    def get_prompt(self, details: dict, preferred_language: str) -> str:
        if preferred_language == LANGUAGES.KISWAHILI.value:
            return details.get('prompt_sw', details.get('prompt_en', ''))
        else:
            return details.get('prompt_en', details.get('prompt', ''))

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.prompt
        inp = inp.strip()
        if len(inp) < 2:
            return f'Please try again. {self.prompt}'
        self.save(customer, inp)
        return None


class SurveyCountyInterrogator(SurveyFreeInputInterrogator):

    MAX_RESPONDENTS_PER_COUNTY = {
        'Nyeri': 3645,
        'Siaya': 1686,
        'Nairobi': 3000,
        'Kiambu': 950,
        'Nakuru': 800,
        'Meru': 556,
        'Murang\'a': 490,
        'Uasin Gishu': 600,
        'Kakamega': 500,
        'Machakos': 500,
        'Makueni': 400,
        'Kitui': 374,
        'Bungoma': 500,
        'Embu': 321,
        'Kisumu': 400,
        'Laikipia': 272,
        'Kirinyaga': 300,
        'Kericho': 400,
        'Trans Nzoia': 400,
        'Nandi': 300,
        'Homa Bay': 200,
        'Busia': 200,
        'Kisii': 200,
        'Nyandarua': 135,
        'Taita Taveta': 132,
        'Mombasa': 250,
        'Kajiado': 150,
        'Migori': 200,
        'Bomet': 200,
        'Baringo': 200,
        'Elgeyo Marakwet': 200,
        'Narok': 82,
        'Vihiga': 150,
        'Nyamira': 100,
        'Kilifi': 67,
        'Tharaka Nithi': 80,
        'Isiolo': 57,
        'Kwale': 45,
        'West Pokot': 19,
        'Mandera': 13,
        'Tana River': 11,
        'Garissa': 13,
        'Samburu': 10,
        'Turkana': 9,
        'Marsabit': 20,
        'Lamu': 8,
        'Wajir': 7
    }

    def get_counties(self):
        return list(self.MAX_RESPONDENTS_PER_COUNTY.keys())

    def get_county_counts(self):
        """
        Return the count of respondents for each county who have completed the survey.
        """
        county_counts = CustomerSurvey.objects.filter(
            survey_title=self.survey_title,
            finished_at__isnull=False,
            responses__County__isnull=False
        ).values('responses__County').annotate(count=Count('id'))

        county_counts_dict = {county: 0 for county in self.get_counties()}
        for item in county_counts:
            county = item['responses__County']
            if county in county_counts_dict:
                county_counts_dict[county] = item['count']
        return county_counts_dict

    def check_county_limit(self, county):
        """
        Check if the number of respondents for the given county has reached the limit.
        """
        county_counts = self.get_county_counts()
        max_respondents = self.MAX_RESPONDENTS_PER_COUNTY.get(county, 0)
        return county_counts.get(county, 0) < max_respondents

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.prompt
        inp = inp.strip()
        if len(inp) < 2:
            return f'Please try again. {self.prompt}'

        res = fuzz_process.extractOne(inp, self.get_counties())
        if res is None or res[1] < 90:
            return f'Could not match county. Please try again. {self.prompt}'
        match = res[0]

        if not self.check_county_limit(match):
            raise StopInterrogation(f"Sorry, this survey has reached the maximum number of respondents from {match}. Thank you for your interest.")

        self.save(customer, match)
        return None


class SurveyConsentInterrogator(SurveyMenuInterrogator):
    # list of tuples (menu item, value to save into survey json)
    menu_items: List[Tuple[str, object]] = None
    question_name: str = None
    preamble: str = ''
    survey_title: str = ''
    stop_choice = None

    def __init__(self, question_key: str, survey_title: str, preferred_language: str, details: dict):
        super().__init__(question_key, survey_title, preferred_language, details)
        self.stop_choice = details.get('stop_choice', self.menu_items[len(self.menu_items) - 1][1])

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:

        if inp is None:
            return self.get_menu_text()
        try:
            item = self.get_menu_item(inp)
        except ValueError:
            LOGGER.error(f'Invalid user input: {inp}')
            # try asking the same question again
            return self.get_menu_text()
        self.save(customer, item[1])
        if item[1] == self.stop_choice:
            raise StopInterrogation


class NameInterrogator(FreeInputInterrogator):
    question = 'What is your name?'
    customer_field = 'name'


class LanguageInterrogator(MenuInterrogator):
    preamble = 'What language do you prefer?\nUnapendelea lugha gani?\n'
    menu_items = [(LANGUAGES.ENGLISH.label, LANGUAGES.ENGLISH.value),
                  (LANGUAGES.KISWAHILI.label, LANGUAGES.KISWAHILI.value)]
    customer_field = 'preferred_language'


class SurveyLanguageInterrogator(MenuInterrogator):
    preamble = 'Please select your preferred language:\nTafadhali chagua lugha yako:\n'
    menu_items = [
        (LANGUAGES.ENGLISH.label, LANGUAGES.ENGLISH.value),
        (LANGUAGES.KISWAHILI.label, LANGUAGES.KISWAHILI.value)
    ]
    customer_field = ""
    survey_title: str


    def __init__(self, survey_title: str):
        self.survey_title = survey_title

    def is_needed(self, customer: Customer) -> bool:
        cs, __ = CustomerSurvey.objects.get_or_create(
            customer_id=customer.id,
            survey_title=self.survey_title
        )
        return not cs.preferred_language

    def save(self, customer: Customer, value):
        cs, __ = CustomerSurvey.objects.get_or_create(
            customer_id=customer.id,
            survey_title=self.survey_title
        )
        cs.preferred_language = value
        cs.save(update_fields=['preferred_language'])

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.get_menu_text()
        try:
            item = self.get_menu_item(inp)
        except ValueError:
            LOGGER.error(f'Invalid user input: {inp}')
            # try asking the same question again
            return self.get_menu_text()

        self.save(customer, item[1])



class GenderInterrogator(MenuInterrogator):
    preamble = 'Are you a man or woman?\n'
    menu_items = [(c[1], c[0]) for c in SEX_SPECIFIED.choices]
    customer_field = 'sex'


class BirthdayInterrogator(DateInterrogator):
    question = 'What is your date of birth?\n'
    min_length = 4
    customer_field = 'dob'

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.question
        if len(inp) < self.min_length:
            return f'Please try again. {self.question}'

        transformer = self.__class__.transformer  # needed to avoid interpreting this as method
        val = transformer(inp) if callable(transformer) else inp
        # If the customer only enters a year for their birthday, we default it to be July 1.
        relative_base = timezone.now()
        relative_base = relative_base.replace(month=7, day=1, hour=0, minute=0, second=0, microsecond=0)
        imported_date = dateparser.parse(val.replace('.', '-'),
                                         settings={
                                             'DATE_ORDER': 'DMY',
                                             'RELATIVE_BASE': relative_base,
                                             'STRICT_PARSING': False,
                                         })
        self.save(customer, imported_date)
        return None


class LocationInterrogator(MenuInterrogator):
    school_name_entered: str
    county_entered: str
    county_matched: str
    county_matched_id: int

    WHAT_SCHOOL = 'What school is closest to your farm?'
    WHAT_SCHOOL_TRY_AGAIN = 'Please try again. What is the name of the school closest to your farm?'
    WHAT_COUNTY = 'What county is your farm in?'
    WHAT_COUNTY_TRY_AGAIN = 'Please try again. What is the name of your county?'
    SELECT_SCHOOL = 'Select your school:\n'
    SELECT_SCHOOL_TRY_AGAIN = 'Please try again. Select your school:\n'
    NONE_OF_THE_ABOVE = 'None of the above'

    @classmethod
    def is_needed(cls, customer: Customer) -> bool:
        return customer.location is None and customer.get_or_create_misc_data().school_name_raw in (None, '')

    def _aq_what_county(self, customer: Customer, inp: None) -> str:
        self._aq_next = self._aq_collect_county
        return self.WHAT_COUNTY

    def _aq_collect_county(self, customer: Customer, inp):
        if len(inp) < 3:
            return self.WHAT_COUNTY_TRY_AGAIN
        self.county_entered = inp
        county_names, _ = zip(*get_county_names_and_ids())
        self.county_matched, _ = fuzz_process.extractOne(inp, county_names)
        # TODO: consider match quality?
        self._aq_next = self._aq_collect_school
        return self.WHAT_SCHOOL

    def _aq_collect_school(self, customer, inp):
        """Takes school name as input and attempts to match against the schools database"""
        if len(inp) < 4:
            return self.WHAT_SCHOOL_TRY_AGAIN
        self.school_name_entered = inp
        df_matches = school_matching.get_matcher().match_df(inp, n=5, county=self.county_matched)
        self._aq_next = self._aq_confirm_school

        self.menu_items = [(self.school_name(school), (school.lat, school.long))
                           for school in df_matches.itertuples()]
        self.menu_items.append((self.NONE_OF_THE_ABOVE, (None, None)))
        return self.get_menu_text(self.SELECT_SCHOOL)

    def _aq_confirm_school(self, customer: Customer, inp):
        """Takes menu item response"""
        try:
            menu_item = self.get_menu_item(inp)
        except ValueError:
            LOGGER.info(f'Invalid user input {inp} for menu: {self.get_menu_text()}')
            return self.get_menu_text(self.SELECT_SCHOOL_TRY_AGAIN)
        customer.get_or_create_misc_data().school_name_raw = self.school_name_entered
        customer.misc_data.county_name_raw = self.county_entered
        customer.misc_data.save()
        lat, long = menu_item[1]
        customer.location = None
        # note: we avoid loading the entire county object, and instead just update the foreign key
        customer.border1_id = dict(get_county_names_and_ids())[self.county_matched]
        if lat is not None and long is not None:
            customer.location = Point(x=long, y=lat, srid=4326)
            if not customer.border3:
                customer.border3 = get_border_for_location(customer.location, 3)
            if customer.border3 and not customer.border2:
                customer.border2 = customer.border3.parent
            if customer.border1 and not customer.border0:
                customer.border0 = customer.border1.parent
        else:
            self._create_agent_task(customer)
        customer.save(update_fields=['location', 'border0', 'border1_id', 'border2', 'border3'])
        # we are done!
        return None

    def _create_agent_task(self, customer: Customer):
        msg = (
            f'Follow up with customer to determine their location. Customer entered:\n'
            f'School name: "{self.school_name_entered}", County: "{self.county_entered}"\n'
            f'Offered choices:\n'
        ) + '\n'.join(f'  {i}. {menu_item[0]}' for i, menu_item in enumerate(self.menu_items[:-1], 1))
        task = Task.objects.create(
            customer=customer,
            description=msg,
            source=customer)
        TaskUpdate.objects.create(
            task=task,
            message=msg,
            status=Task.STATUS.new,
        )
        return None

    def school_name(self, school: namedtuple('School', ['name', 'County', 'SUB_COUNTY', 'Ward'])):
        """Constructs school name that's as specific as possible"""
        parts = [part for part in (school.name, school.County) if part]
        return ', '.join(parts)

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        return self._aq_next(customer, inp)
        pass

    _aq_next = _aq_what_county


class FarmSizeInterrogator(MenuInterrogator):
    preamble = 'What is your farm size?\n'
    menu_items = [
        (name.replace('&ndash;', ' - ') + (' acres' if i > 0 else ' acre'), val)
        for i, (val, name) in enumerate(FARM_SIZES_SPECIFIED.choices)
    ]
    customer_field = 'farm_size'


class FarmOwnershipInterrogator(MenuInterrogator):
    preamble = 'Do you own your farm?\n'
    menu_items = [('Yes', True), ('No', False)]
    customer_field = 'owns_farm'


class CropsInterrogator(Interrogator):
    QUESTION = 'Please enter 2 to 3 main crops that you grow, separated by comma or spaces. Or type "none"'
    TRY_AGAIN = 'Please try again: enter main crops that you grow. You can also type "none".'

    @classmethod
    def is_needed(cls, customer: Customer) -> bool:
        if customer.get_or_create_misc_data().crops_raw:
            return False
        return customer.commodities.filter(commodity_type=Commodity.CROP).count() == 0

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.QUESTION
        if len(inp) < 3:
            return self.TRY_AGAIN
        misc_data = customer.get_or_create_misc_data()
        misc_data.crops_raw = inp
        if re.sub(r'[^\w]+', ' ', inp).strip().lower() == 'none':
            # remove all crops
            customer.commodities.set(c for c in customer.commodities.all() if c.commodity_type != Commodity.CROP)
        else:
            commodities, misc_data.crops_unmatched = self.guess_crops(inp)
            customer.commodities.add(*commodities)
        self.save(customer, misc_data)
        return None

    def guess_crops(self, inp: str) -> Tuple[List[Commodity], int]:
        crops_map = get_commodity_map(Commodity.CROP)
        matches, unmatched = fuzzy_matching.find_choices_raw(inp, list(crops_map.keys()))
        return [crops_map[match] for match in matches], unmatched

    def save(self, customer: Customer, misc_data):
        customer.save()
        misc_data.save()


class LiveStockInterrogator(Interrogator):
    QUESTION = 'Please enter 2 to 3 main livestock (animals) you keep, separated by comma or spaces. Or type "none"'
    TRY_AGAIN = 'Please try again: enter main animals you keep. You can also type "none".'

    @classmethod
    def is_needed(cls, customer: Customer) -> bool:
        if customer.get_or_create_misc_data().livestock_raw:
            return False
        return customer.commodities.filter(commodity_type=Commodity.LIVESTOCK).count() == 0

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.QUESTION
        if len(inp) < 3:
            return self.TRY_AGAIN
        misc_data = customer.get_or_create_misc_data()
        misc_data.livestock_raw = inp
        if re.sub(r'[^\w]+', ' ', inp).strip().lower() == 'none':
            customer.commodities.set(c for c in customer.commodities.all() if c.commodity_type != Commodity.LIVESTOCK)
        else:
            commodities, misc_data.livestock_unmatched = self.guess_livestock(inp)
            customer.commodities.add(*commodities)
        self.save(customer, misc_data)
        return None

    def guess_livestock(self, inp: str) -> Tuple[List[Commodity], int]:
        livestock_map = get_commodity_map(Commodity.LIVESTOCK)
        matches, unmatched = fuzzy_matching.find_choices_raw(inp, list(livestock_map.keys()))
        return [livestock_map[match] for match in matches], unmatched

    def save(self, customer: Customer, misc_data):
        customer.save()
        misc_data.save()


class CropsFailedInterrogator(LetItRainMenuInterrogator):
    preamble = 'Have your crops ever failed?\n'
    menu_items = [('Yes', True), ('No', False)]
    letitrain_field = 'crops_have_failed'


class CropsInsuranceInterrogator(LetItRainMenuInterrogator):
    preamble = 'Do you have crop insurance?\n'
    menu_items = [('Yes', True), ('No', False)]
    letitrain_field = 'has_crop_insurance'


class ReceivesForecastsInterrogator(LetItRainMenuInterrogator):
    preamble = 'Do you receive weather forecasts?\n'
    menu_items = [('Yes', True), ('No', False)]
    letitrain_field = 'receives_weather_forecasts'

    @classmethod
    def is_needed(cls, customer: Customer) -> bool:
        let_it_rain_data = customer.get_or_create_letitrain_data()
        # If we have not recorded the forecast frequency, restart
        # the question line here so the customer has some context.
        return let_it_rain_data.forcast_frequency_days is None


class WeatherForcastFrequencyInterrogator(LetItRainMenuInterrogator):
    preamble = 'How many days between each weather forecast?'
    menu_items = [('Daily', 1),
                  ('Twice per week', 3),
                  ('Weekly', 7),
                  ('Every 2 weeks', 14),
                  ('Monthly', 31),
                  ('Once per season', 180)]
    letitrain_field = 'forcast_frequency_days'


class WeatherForcastSourceInterrogator(LetItRainMenuInterrogator):
    preamble = 'Who provides your weather forecast?\n'
    menu_items = [('iShamba', 'ishamba'), ('Shamba Shape Up', 'ssu'), ('Other', 'other')]
    letitrain_field = 'weather_source'


class CertifiedSeedsInterrogator(LetItRainMenuInterrogator):
    preamble = 'Do you plant certified seeds?\n'
    menu_items = [('Yes', True), ('No', False)]
    letitrain_field = 'uses_certified_seed'


class FertilizerInterrogator(LetItRainMenuInterrogator):
    preamble = 'Do you use organic or synthetic fertilizer?\n'
    menu_items = [
        (value, key)
        for key, value in CustomerLetItRainData.FertilizerTypes.choices
        if key is not None
    ]
    letitrain_field = 'fertilizer_type'


class ExperiencedFloodsInterrogator(LetItRainMenuInterrogator):
    preamble = 'Have you experienced flooding?\n'
    menu_items = [('Yes', True), ('No', False)]
    letitrain_field = 'has_experienced_floods'


class ExperiencedDroughtInterrogator(LetItRainMenuInterrogator):
    preamble = 'Have you experienced droughts?\n'
    menu_items = [('Yes', True), ('No', False)]
    letitrain_field = 'has_experienced_droughts'


class ExperiencedPestsInterrogator(LetItRainMenuInterrogator):
    preamble = 'Have you experienced pests?\n'
    menu_items = [('Yes', True), ('No', False)]
    letitrain_field = 'has_experienced_pests'


class ExperiencedDiseaseInterrogator(LetItRainMenuInterrogator):
    preamble = 'Have you experienced crop disease?\n'
    menu_items = [('Yes', True), ('No', False)]
    letitrain_field = 'has_experienced_diseases'


class LetItRainDateGuessInterrogator(LetItRainDateInterrogator):
    question = 'When do you think the rains will start?'
    min_length = 4
    letitrain_field = 'guesses'
    max_guesses = 3

    @classmethod
    def is_needed(cls, customer: Customer) -> bool:
        letitrain_data = customer.get_or_create_letitrain_data()
        guess_count = len(letitrain_data.guesses) if letitrain_data.guesses is not None else 0
        return guess_count < LetItRainDateGuessInterrogator.max_guesses

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            return self.question
        if len(inp) < self.min_length:
            return f'Please try again. {self.question}'

        transformer = self.__class__.transformer  # needed to avoid interpreting this as method
        val = transformer(inp) if callable(transformer) else inp
        imported_date = dateparser.parse(val.replace('.', '-'),
                                         settings={
                                             'DATE_ORDER': 'DMY',
                                             'STRICT_PARSING': True,
                                         })
        if imported_date is None:
            return f'Please try again. {self.question}'
        self.save(customer, imported_date)
        return None

    def save(self, customer: Customer, value):
        letitrain_data = customer.get_or_create_letitrain_data()
        if letitrain_data.guesses is None:
            letitrain_data.guesses = [value]
        else:
            letitrain_data.guesses.append(value)
        letitrain_data.save(update_fields=[self.letitrain_field])


class LetItRainDateFirstGuessInterrogator(LetItRainDateGuessInterrogator):
    question = 'Please enter your 1st guess. When do you think the rains will start?'


class LetItRainDateSecondGuessInterrogator(LetItRainDateGuessInterrogator):
    question = 'Please enter your 2nd guess. When do you think the rains will start?'


class LetItRainDateThirdGuessInterrogator(LetItRainDateGuessInterrogator):
    question = 'Please enter your 3rd guess. When do you think the rains will start?'


class FsmInterrogatorState:
    """Abstract base class for FSM-based interrogators."""
    def __init__(self, parent: 'FsmInterrogator'):
        self.parent = parent

    def on_enter(self, customer: Customer) -> Optional['FsmInterrogatorState']:
        """Returns self to accept processing, another state instance to forward
        processing to another state, or None to reject and signal that interrogation
        is finished.
        """
        # default implementation - accept
        return self

    def question(self, customer: Customer) -> Optional[str]:
        raise NotImplementedError()

    def on_response(self, resp: str, customer: Customer) -> Optional['FsmInterrogatorState']:
        raise NotImplementedError()


class FsmInterrogator(Interrogator):
    """
    State machine-based interrogator. This is meant for more complicated cases where the flow leads through
    a variable sequence of states.

    The "aq" interrogator interface is driven by the needs of USSD request/response: we receive the Answer
    to the prior question, and in return we send in a new Question - thus "aq". However, this is hard on
    brain when writing and organizing code, because we are wired to think in terms of Q&A, rather than A&Q.

    The FsmInterrogator attempts to help with this, by making each state responsible for:
     - asking the question
     - processing the response when it comes back
     - choosing the next state to forward to

    The concrete subclasses should overwrite the inital_state() method, and should contain the various
    state classes, but otherwise should not have to change the aq() method definition.
    """
    state: FsmInterrogatorState = None

    def initial_state(self, customer: Customer) -> Optional[FsmInterrogatorState]:
        raise NotImplementedError()

    def _enter_state(self, state: FsmInterrogatorState, customer: Customer):
        while self.state is not state and state is not None:
            state, self.state = state.on_enter(customer), state

        # at this point, we either entered a state, or there are no states left
        self.state = state
        return

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        if inp is None:
            self._enter_state(self.initial_state(customer), customer)
            if self.state is None:
                return None
            else:
                return self.state.question(customer)
        self._enter_state(self.state.on_response(inp, customer), customer)
        return self.state.question(customer) if self.state else None


def now():
    """Defined here so we can mock it in tests"""
    return datetime.now()


class CropsConfirmer(FsmInterrogator):

    @classmethod
    def is_needed(cls, customer: Customer) -> bool:
        return True

    def initial_state(self, customer: Customer) -> Optional[FsmInterrogatorState]:
        return CropsConfirmer.ConfirmCropsState(parent=self)

    class ConfirmCropsState(FsmInterrogatorState):
        CORRECT = "That's correct"
        ADD = "Add crops"
        REMOVE = "Remove crops"
        PREAMBLE1 = "We don't have any crops on record for you.\n"
        PREAMBLE2 = "We think you grow these crops: {}\n"
        menu_items: MenuItems = [(CORRECT, CORRECT), (ADD, ADD), (REMOVE, REMOVE)]

        def question(self, customer: Customer) -> Optional[str]:
            crops = list(customer.commodities.filter(commodity_type=Commodity.CROP))
            if not crops:
                self.menu_items = self.menu_items[:2]  # don't list remove as option
                return get_menu_text(self.PREAMBLE1, self.menu_items)
            return get_menu_text(
                self.PREAMBLE2.format(', '.join(c.name for c in crops)),
                self.menu_items
            )

        def on_response(self, resp: str, customer: Customer) -> Optional['FsmInterrogatorState']:
            try:
                _, action = get_menu_item(resp, self.menu_items)
                if action == self.ADD:
                    return CropsConfirmer.EnterCropState(self.parent)
                elif action == self.REMOVE:
                    return CropsConfirmer.RemoveCropState(self.parent)
                elif action == self.CORRECT:
                    return CropsConfirmer.EnterPlantingDatesState(self.parent)
                assert False, 'We should not get here!!!'
            except ValueError as e:
                LOGGER.warning(f'Invalid customer input {e}')
                return self

    class EnterCropState(FsmInterrogatorState):
        Q = 'What would you like to add? (One crop at the time, please.)'

        def question(self, customer: Customer) -> Optional[str]:
            return self.Q

        def on_response(self, resp: str, customer: Customer) -> Optional['FsmInterrogatorState']:
            crop_name = re.sub(r'[^\w]+', ' ', resp).strip().lower()
            if crop_name in ('', 'none'):
                return CropsConfirmer.ConfirmCropsState(self.parent)
            return CropsConfirmer.SelectForAddingState(parent=self.parent, crop_name=crop_name)

    class SelectForAddingState(FsmInterrogatorState):
        SELECT = 'Select one to add:\n'

        menu_items: MenuItems

        def __init__(self, parent: FsmInterrogator, crop_name: str):
            super().__init__(parent)
            self.crop_name = crop_name

        def question(self, customer: Customer) -> Optional[str]:
            crops_map = get_commodity_map(Commodity.CROP)

            # Deduplicate the matched crops, while preserving order. Take top 5 matches at most.
            matches: Dict[Commodity, None] = {}
            for key, _ in fuzz_process.extractBests(self.crop_name, crops_map.keys(), limit=10):
                commodity = crops_map[key]
                if commodity not in matches:
                    matches[commodity] = None
                    if len(matches) == 5:
                        break
            crops = list(matches.keys())
            self.menu_items = [(crop.name, crop.name.lower()) for crop in crops]
            self.menu_items.append(('None of the above', None))
            return get_menu_text(self.SELECT, self.menu_items)

        def on_response(self, resp: str, customer: Customer) -> Optional['FsmInterrogatorState']:
            try:
                _, crop_name = get_menu_item(resp, self.menu_items)
                crop_name: str
                if crop_name:
                    customer.commodities.add(get_commodity_map(Commodity.CROP)[crop_name.lower()])
                return CropsConfirmer.ConfirmCropsState(parent=self.parent)
            except ValueError as e:
                LOGGER.warning(f'Invalid customer input {e}')

    class RemoveCropState(FsmInterrogatorState):
        SELECT = 'Select crop to remove:\n'
        menu_items: MenuItems

        def question(self, customer: Customer) -> Optional[str]:
            crops = customer.commodities.filter(commodity_type=Commodity.CROP)
            self.menu_items = [(c.name, c.name.lower()) for c in crops]
            self.menu_items.append(('Go back', None))
            return get_menu_text(self.SELECT, self.menu_items)

        def on_response(self, resp: str, customer: Customer) -> Optional['FsmInterrogatorState']:
            try:
                _, crop_name = get_menu_item(resp, self.menu_items)
                crop_name: str
                if crop_name:
                    crop = get_commodity_map(Commodity.CROP)[crop_name.lower()]
                    customer.commodities.remove(crop)
                return CropsConfirmer.ConfirmCropsState(self.parent)
            except ValueError as e:
                LOGGER.warning(f'Invalid customer input: {e}')
                return self

    class EnterPlantingDatesState(FsmInterrogatorState):
        annuals_names: List[str]
        first: bool = True

        def on_enter(self, customer: Customer) -> Optional['FsmInterrogatorState']:
            annuals = self.annuals_with_no_history(customer)
            if not annuals:
                # reject, since there is nothing to do. We are also the last state.
                return None
            # Store list of annuals, so we don't have to keep querying for it each time.
            # But don't store the full objects, to avoid too much serialization.
            self.annuals_names = [a.name for a in annuals]
            return self

        def question(self, customer: Customer) -> Optional[str]:
            crop = self.annuals_names[0]
            if self.first:
                expl = 'To customize our advice even better, we need to know your planting schedule. '
            else:
                expl = ''
            q = f'{expl}Please enter the approximate planting date for your {crop}. (e.g. 15/03/2021 or just 15/03)'
            self.first = False
            return q

        def on_response(self, resp: str, customer: Customer) -> Optional['FsmInterrogatorState']:
            if len(resp) < 3:
                # we'll try again
                return self

            planting_date = dateparser.parse(resp.replace('.', '-'), settings={'DATE_ORDER': 'DMY'})
            current_time = now()

            if planting_date and not (
                -timedelta(days=60) < planting_date - current_time < timedelta(days=60)
            ):
                # Ensure that the date is within 60 days of today. Try again.
                return self

            # If we made it this far, we either collected valid date within 60 days of now,
            # or customer typed something non-trivial that can't be parsed as date. Either way
            # we choose to move on, and so we pop the crop_name from the list of annuals.
            crop_name, self.annuals_names = self.annuals_names[0], self.annuals_names[1:]
            if planting_date:
                crop = get_commodity_map(Commodity.CROP)[crop_name.lower()]
                LOGGER.info(f'Creating CropHistory for customer {customer.id}, {crop_name}: {planting_date}')
                CropHistory(customer=customer, commodity=crop, date_planted=planting_date).save()
            else:
                LOGGER.warning(
                    f'Failed to parse customer response "{resp}": {customer.id}, {crop_name}: {planting_date}')
                # ToDo: create agent task
            # check if there are any more crops to process
            return self if self.annuals_names else None

        def annuals_with_no_history(self, customer: Customer) -> List[Commodity]:
            annuals = list(
                customer.commodities.filter(commodity_type=Commodity.CROP, season_length_days__isnull=False)
            )
            if not annuals:
                return annuals
            # Look for any recent crop histories. We'll define recent as planting date approximately within
            # the typical season length.
            crop_histories = list(customer.crophistory_set.filter(commodity__in=annuals))
            annuals_with_crop_history = {
                ch.commodity for ch in crop_histories
                if ch.date_planted + timedelta(days=1.2 * ch.commodity.season_length_days) > now().date()
            }
            # remove from the annuals list any that already have crop history
            return [a for a in annuals if a not in annuals_with_crop_history]

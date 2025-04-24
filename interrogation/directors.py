from typing import Any, List, Optional, Tuple, Type

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from customers.models import Customer, CustomerLetItRainData, CustomerSurvey
from interrogation.interface import (Director, Interrogator, StopInterrogation,
                                     SurveyInterrogator, register_director)
from interrogation.interrogators import *
from interrogation.tasks import maybe_register_customer

# How long to wait before sending welcome SMS (seconds)
WELCOME_SMS_WAIT = 4 * 60
WELCOME_SMS_SHORT_WAIT = 30


class BaseDirector(Director):
    """
    BaseDirector provides base implementation of the Director interface, built using the Interrogator
    abstraction. The Director does its work by delegating the "aq()" method to the current interrogator,
    cycling through the interrogators until the interrogation is over.

    Subclasses can configure the Director by specifying the following class level attributes:
     * interrogators - list of Interrogator classes to use
     * hello - optional greeting at the start of the Session
     * goodbye - optional greeting at the end of the Session
     * bid - value to bid if any of the Interrogators are needed for the customer
    """
    interrogator: Optional[Interrogator] = None  # current interrogator
    interrogators: List[Type[Interrogator]]  # relevant interrogator classes - used to configure subclasses
    past_interrogators: List[Type[Interrogator]]  # already completed interrogators
    hello: str = ''
    goodbye: str = ''
    bid: float = 1

    @classmethod
    def make_bid(cls, customer: Customer, survey_title: str = '') -> float:
        if survey_title:
            # Handle survey bidding separately (in BaseSurveyDirector)
            return 0
        for interrogator_cls in cls.interrogators:
            if interrogator_cls.is_needed(customer):
                return cls.bid
        return 0

    def __init__(self):
        self.past_interrogators = []

    def next_interrogator(self, customer: Customer) -> Optional[Interrogator]:
        assert self.interrogator is None
        interrogator_cls = next(
            (interrogator for interrogator in self.interrogators
             if interrogator not in self.past_interrogators and interrogator.is_needed(customer)),
            None
        )
        return interrogator_cls() if interrogator_cls else None

    def get_hello(self, customer: Customer) -> str:
        return self.hello

    def get_goodbye(self, customer: Customer) -> str:
        return self.goodbye

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        while True:
            if self.interrogator is None:
                assert inp is None, f'Text input {inp} present with no interrogator'
                self.interrogator = self.next_interrogator(customer)
                if self.interrogator is None:
                    # no more interrogators, we are done
                    return None
            question = self.interrogator.aq(customer, inp)
            if question is not None:
                return question
            # the interrogator has finished, move on to the next one
            self.past_interrogators.append(self.interrogator.__class__)
            self.interrogator = None
            inp = None


@register_director
class RegistrationDirector(BaseDirector):
    """
    Director implementation that simply goes through a predefined list of interrogators and checks
    with each of them if they are needed.
    """
    interrogators: List[Type[Interrogator]] = [
        LocationInterrogator,
        FarmSizeInterrogator,
        GenderInterrogator,
        CropsInterrogator,
        CropsConfirmer,
        BirthdayInterrogator,
        LiveStockInterrogator,
        NameInterrogator,
    ]
    bid = 10

    hello = 'Welcome to iShamba. If you get disconnected, please redial (free) to continue.\n'
    goodbye = 'Thank you for completing the questionnaire. Goodbye.\n'

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        ret = super().aq(customer, inp)

        if customer.is_registered:
            return ret

        if ret is None:
            # Unregistered customer completed data intake. Queue up sending of welcome message
            # with just slight delay, to allow customer to read final response from USSD.
            maybe_register_customer.s(
                customer_id=customer.id, phone_number=customer.main_phone, timestamp=None
            ).set(countdown=WELCOME_SMS_SHORT_WAIT).delay()
            return ret

        # Session is still ongoing. Check if we crossed minimum registration requirement, and if yes
        # schedule conditional sending of welcome SMS in case customer does not come back to continue
        # with the session.
        if not NameInterrogator.is_needed(customer) and not LocationInterrogator.is_needed(customer):
            transaction.on_commit(
                lambda: maybe_register_customer.s(
                    customer_id=customer.id,
                    phone_number=customer.main_phone,
                    timestamp=timezone.now()
                ).set(countdown=WELCOME_SMS_WAIT).delay()
            )
        return ret


@register_director
class LetItRainDirector(BaseDirector):
    """
    Director implementation that simply goes through a predefined list of interrogators and checks
    with each of them if they are needed. For the game data collection to be complete, the
    customer must finish all of the required fields for registration plus all of the fields
    required for the game data collection.
    # TODO: Test
    """
    interrogators: List[Type[Interrogator]] = [
        LocationInterrogator,
        GenderInterrogator,
        BirthdayInterrogator,
        NameInterrogator,
        LetItRainDateFirstGuessInterrogator,  # Let the customer enter one guess after personal details are collected
        FarmOwnershipInterrogator,
        FarmSizeInterrogator,
        LiveStockInterrogator,
        CropsInterrogator,
        CropsConfirmer,
        CertifiedSeedsInterrogator,
        FertilizerInterrogator,
        LetItRainDateSecondGuessInterrogator,  # Let the customer enter one guess after farm details are collected
        CropsFailedInterrogator,
        CropsInsuranceInterrogator,
        ReceivesForecastsInterrogator,
        WeatherForcastFrequencyInterrogator,
        WeatherForcastSourceInterrogator,
        ExperiencedFloodsInterrogator,
        ExperiencedDroughtInterrogator,
        ExperiencedPestsInterrogator,
        ExperiencedDiseaseInterrogator,
        LetItRainDateThirdGuessInterrogator  # Let the customer enter one guess after climate impact details are collected
    ]

    bid = 1

    hello = 'Welcome to iShamba. If you get disconnected, please redial (free) to continue.\n'
    goodbye = 'Thank you for completing the questionnaire. Goodbye.\n'

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        ret = super().aq(customer, inp)

        letitrain_data = customer.get_or_create_letitrain_data()
        if customer.is_registered and letitrain_data.is_complete:
            return ret

        # Save these only once to prevent pounding the db on every response
        if letitrain_data.season is None or letitrain_data.season == '':
            letitrain_data.season = letitrain_data.current_season
            letitrain_data.data_source = CustomerLetItRainData.DataSources.USSD
            letitrain_data.save(update_fields=['season', 'data_source'])

        if ret is None:
            # Unregistered customer completed data intake. Queue up sending of welcome message
            # with just slight delay, to allow customer to read final response from USSD.
            # TODO: should phone_number be their main or the one they started the USSD session with?
            maybe_register_customer.s(
                customer_id=customer.id, phone_number=customer.main_phone, timestamp=None
            ).set(countdown=WELCOME_SMS_SHORT_WAIT).delay()
            return ret

        # Session is still ongoing. Check if we crossed minimum registration requirement, and if yes
        # schedule conditional sending of welcome SMS in case customer does not come back to continue
        # with the session.
        if not NameInterrogator.is_needed(customer) and not LocationInterrogator.is_needed(customer):
            transaction.on_commit(
                lambda: maybe_register_customer.s(
                    customer_id=customer.id,
                    phone_number=customer.main_phone,
                    timestamp=timezone.now()
                ).set(countdown=WELCOME_SMS_WAIT).delay()
            )
        return ret


class BaseSurveyDirector(Director):
    """
    A Director implementation that simply goes through a predefined list of survey questions
    (and their) interrogators and checks with each of them if they are needed. For the data
    collection to be complete, the customer must finish all of the questions.

    Note that for surveys, the director iterates through a series of questions which may
    use the same interrogator repeatedly. The resulting data is stored in a JSON field of
    the CustomerSurvey table, not in the customer record. Each question is identified by a
    unique question key, which is used both to identify the interrogator to use as well as
    the key within the JSON structure to store the customer's answer.

    Subclasses can configure the BaseSurveyDirector by specifying the following class level attributes:
     * questions - list of questions and their corresponding Interrogator classes to use
     * hello - optional greeting at the start of the Session
     * goodbye - optional greeting at the end of the Session
     * bid - value to bid if any of the Interrogators are needed for the customer
     * survey_title - a unique title to identify this survey
    """
    question: Optional[Tuple[str, Type[SurveyInterrogator], Optional[Any]]] = None  # current question and corresponding interrogator
    questions: List[Tuple[str, Type[SurveyInterrogator], Optional[Any]]]  # the questions and interrogator classes for this survey
    past_questions: List[str]  # already completed interrogators
    hello: str = ''
    goodbye: str = ''
    bid: float = 1
    survey_title: str = ''
    user_cancelled: bool

    @classmethod
    def make_bid(cls, customer: Customer, survey_title: str = '') -> float:
        if survey_title.lower() != cls.survey_title.lower():
            return 0
        cs = CustomerSurvey.objects.filter(
            customer_id=customer.id,
            survey_title=survey_title
        ).first()
        if cs and cs.is_finished:
            return 0
        return cls.bid

    def __init__(self):
        self.past_questions = []
        self.user_cancelled = False

    def next_question(self, customer: Customer) -> Optional[Tuple[str, Type[SurveyInterrogator], Optional[Any]]]:
        assert self.question is None
        cs, created = CustomerSurvey.objects.get_or_create(
            customer_id=customer.id,
            survey_title=self.survey_title,
            defaults={
                'responses': {},
                'data_source': CustomerSurvey.DataSources.USSD.value
            }
        )

        for question in self.questions:
            if self.user_cancelled:
                break
            if issubclass(question[1], SurveyInterrogator):
                if question[0] not in self.past_questions and question[0] not in cs.responses:
                    return question
            elif question[1] == SurveyLanguageInterrogator:
                if question[1](survey_title=self.survey_title).is_needed(customer):
                    return question
            else:
                if question[1].is_needed(customer):
                    return question

        # If no more questions or user cancelled, mark the CustomerSurvey as finished
        cs.finished_at = timezone.now()
        cs.save()
        return None

    def get_hello(self, customer: Customer) -> str:
        return self.hello

    def get_goodbye(self, customer: Customer) -> str:
        return self.goodbye

    def check_predicates(self):
        pass

    def aq(self, customer: Customer, inp: Optional[str]) -> Optional[str]:
        try:
            while True:
                if self.question is None:
                    assert inp is None, f'Text input {inp} present with no interrogator'
                    self.question = self.next_question(customer)
                    if self.question is None:
                        # no more questions, we are done
                        return None

                self.check_predicates()

                question_key = self.question[0]

                # Retrieve preferred language from CustomerSurvey
                cs = CustomerSurvey.objects.get(customer_id=customer.id, survey_title=self.survey_title)

                # Instantiate the corresponding SurveyInterrogator
                if issubclass(self.question[1], SurveyInterrogator):
                    interrogator: SurveyInterrogator = self.question[1](
                        question_key=question_key,
                        survey_title=self.survey_title,
                        preferred_language=cs.preferred_language,
                        details=self.question[2] if len(self.question) > 2 else None,
                    )
                elif self.question[1] == SurveyLanguageInterrogator:
                    interrogator: SurveyLanguageInterrogator = self.question[1](survey_title=self.survey_title)
                else:
                    interrogator: Interrogator = self.question[1]()
                next_question = interrogator.aq(customer, inp)
                if next_question is not None:
                    return next_question
                # the interrogator has finished, move on to the next one
                self.past_questions.append(question_key)
                self.question = None
                inp = None
        except StopInterrogation as e:
            # The user cancelled, so mark the CustomerSurvey as finished
            self.user_cancelled = True
            cs = CustomerSurvey.objects.get(
                customer_id=customer.id,
                survey_title=self.survey_title,
            )
            cs.finished_at = timezone.now()
            cs.save()
            if e.goodbye_message != None:
                self.goodbye = e.goodbye_message
            return None


@register_director
class CIATDietQualitySurveyDirector(BaseSurveyDirector):
    """
    A Director implementation that simply goes through a predefined list of survey questions
    (and their) interrogators and checks with each of them if they are needed. For the data
    collection to be complete, the customer must finish all of the questions.

    Note that for surveys, the director iterates through a series of questions which may
    use the same interrogator repeatedly. The resulting data is stored in a JSON field of
    the CustomerSurvey table, not in the customer record. Each question is identified by a
    unique question key, which is used both to identify the interrogator to use as well as
    the key within the JSON structure to store the customer's answer.

    Subclasses can configure the BaseSurveyDirector by specifying the following class level attributes:
     * questions - list of questions and their corresponding Interrogator classes to use
     * hello - optional greeting at the start of the Session
     * goodbye - optional greeting at the end of the Session
     * bid - value to bid if any of the Interrogators are needed for the customer
     * survey_start - the date that this customer started the survey
     * survey_title - a unique title to identify this survey
    """

    def check_predicates(self):
        total_respondents = CustomerSurvey.objects.filter(survey_title=self.survey_title, finished_at__isnull=False).count()
        if total_respondents > settings.CIAT_DIET_QUALITY_SURVEY_MAX_RESPONDENTS:
            raise StopInterrogation(
                "Thank you for your interest. This survey has already reached the maximum number of respondents."
            )

    survey_title: str = 'CIATDietQuality'
    hello: str = ''
    goodbye: str = ''
    bid: float = 2
    questions: list[tuple[str, Type[SurveyInterrogator], Optional[Any]]] = [  # the questions and interrogator classes for this survey
        ('Pre-question', SurveyLanguageInterrogator,),
        (
            'Intro',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Welcome. If you get disconnected, please redial (free) to continue.\n',
                'preamble_sw': 'Karibu. Ukitenganishwa, tafadhali bonyeza tena (bila malipo) ili kuendelea.\n',
                'menu_items': [('Next', 'ok')],
            },
        ),
        (
            'Intro_2',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Our system can detect unlikely responses, please answer honestly.\n',
                'preamble_sw': 'Mfumo wetu unaweza kugundua majibu yasiyotarajiwa, tafadhali jibu kwa uaminifu.\n',
                'menu_items': [('Next', 'ok')],
            },
        ),
        (
            'Consent',
            SurveyConsentInterrogator,
            {
                'preamble_en': 'Your participation is voluntary and responses are anonymous.\n',
                'preamble_sw': 'Kushiriki kwako ni kwa hiari na majibu hayatambuliwi.\n',
                'menu_items_en': [('Participate', 'agree'), ('Stop', 'stop')],
                'menu_items_sw': [('Shiriki', 'agree'), ('Acha', 'stop')],
                'stop_choice': 'stop',
            },
        ),
        (
            'Sex',
            SurveyGenderInterrogator,
            {
                'preamble_en': 'What is your gender?\n',
                'preamble_sw': 'Jinsia lako ni?\n',
                'menu_items_en': [('Male', 'm'), ('Female', 'f')],
                'menu_items_sw': [('Mwanaume', 'm'), ('Mwanamke', 'f')]
            }
         ),
        (
            'Age',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'How old are you?\n',
                'preamble_sw': 'Una miaka mingapi?\n',
                'menu_items_en': [
                    ('Under 18', '<18'),
                    ('18-24 years', '18-24'),
                    ('25-34 years', '25-34'),
                    ('35-44 years', '35-44'),
                    ('Above 44 years', '>44'),
                ],
                'menu_items_sw': [
                    ('Chini ya miaka 18', '<18'),
                    ('Miaka 18-24', '18-24'),
                    ('Miaka 25-34', '25-34'),
                    ('Miaka 35-44', '35-44'),
                    ('Zaidi ya miaka 44', '>44'),
                ],
            },
        ),
        (
            'County',
            SurveyCountyInterrogator,
            {
                'prompt_en': 'Which county do you live in?\n',
                'prompt_sw': 'Je, unaishi katika kaunti gani?\n',
            }
        ),
        (
            'Intro_3',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'We will now ask what YOU ate YESTERDAY. If you did not eat any of the foods listed, or don\'t recognise them, answer no.\n',
                'preamble_sw': 'Sasa tutauliza ulikula nini JANA. Iwapo hukula chochote kati ya vyakula vilivyoorodheshwa, au huvitambui, jibu hapana.?\n',
                'menu_items': [('Next', 'ok')],
            }
        ),
        (
            'Intro_4',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'If you have eaten one, or more, of the listed foods, answer yes.\n',
                'preamble_sw': 'Ikiwa umekula moja, au zaidi, ya vyakula vilivyoorodheshwa, jibu ndiyo.\n',
                'menu_items_en': [('Start', 'ok')],
                'menu_items_sw': [('Anza', 'ok')],
            }
        ),
        (
            'Q1',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Yesterday, did you eat any of the following foods: Maize ugali, maize porridge, rice, bread, chapati, injera, pasta, or noodles?\n',
                'preamble_sw': 'Je, jana, ulikula yoyote ya vyakula vifuatavyo:Ugali wa mahindi, uji wa mahindi, mchele, mkate, chapati, anjera, pasta / tambi, au noodles / tambi?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q2',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Ugali made from millet or sorghum, porridge made from millet or sorghum, green maize, githeri, oats, or popcorn?\n',
                'preamble_sw': 'Ugali iliyotengenezwa kwa millet / wimbi au sorghum / mtama, uji uliotengenezwa kwa millet / wimbi au sorghum / mtama, mahindi mabichi, githeri, shayiri / oats, au popcorn?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q3',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Irish potato, white sweet potato, green banana, nduma, yam, or cassava?\n',
                'preamble_sw': 'Irish potato, viazi vitamu vyeupe, ndizi mbichi, arrowroot, yam, au muhogo?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q4',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Beans, githeri, green gram, kamande, pigeon peas, chickpeas, or green peas?\n',
                'preamble_sw': 'Maharage, githeri, pojo / ndengu, kamande / ndengu za kijani, mbaazi, njegere, au pojo / ndengu?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q5',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Yesterday, did you eat any of the following vegetables: Carrots, pumpkin, butternut, or sweet potato that is orange or yellow inside?\n',
                'preamble_sw': 'Je, jana ulikula mboga yoyote ifuatayo: Karoti, malenge, mronge, au viazi vitamu ambavyo ni vya rangi ya machungwa ndani?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q6a',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Sukuma wiki, Ethiopian kale, spinach, managu, terere, saget, or kunde?\n',
                'preamble_sw': 'Sukuma wiki, khandira, mchicha, majani ya nightshade, majani ya amaranth, mmea wa buibui wa Kiafrika, au majani ya kunde?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q6b',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Broccoli, pumpkin leaves, mrenda, nderema, mitoo, or mchunga?\n',
                'preamble_sw': 'Broccoli, majani ya malenge, jute mallow, mchica wa malabar, marejea au mchunga?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q7a',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Tomatoes, cabbage, green capsicum, mushrooms, or cauliflower?\n',
                'preamble_sw': 'Nyanya, kabichi, hoho ya kijani kibichi, uyoga, au kolifulawa?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q7b',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Cucumber, French beans, lettuce, eggplant, or courgette?\n',
                'preamble_sw': 'Tango, maharagwe ya Ufaransa, lettuce, biliganya, au mung\'unye?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q8',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Yesterday, did you eat any of the following fruits: Pawpaw, mango, passion fruit, or matunda ya damu?\n',
                'preamble_sw': 'Je, jana ulikula matunda yoyote yafuatayo: Papai, embe lililoiva, tunda la passioni, au matunda ya damu?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q9',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Orange, mandarin, or grapefruit?\n',
                'preamble_sw': 'Chungwa, tangerine, au grapefruit?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q10a',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Ripe banana, pineapple, avocado, watermelon, or thorn melon?\n',
                'preamble_sw': 'Ndizi mbivu, nanasi, parachichi, tikiti maji, au kiwano?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q10b',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Apple, pear, grapes, or guava?\n',
                'preamble_sw': 'Apple, pea, zabibu, au mapera?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q11',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Yesterday, did you eat any of the following sweets: Cakes, queencakes, biscuits, or kaimati?\n',
                'preamble_sw': 'Je, jana ulikula yoyote ya switi/pipi zifuatazo: Keki, keki ya kikombe, biskuti tamu, au kaimati?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q12',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Sweets, chocolates, ice cream, or ice lollies?\n',
                'preamble_sw': 'Pipi, chokoleti, aiskrimu, au aiskrimu za vijiti?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Bogus_Item',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Yesterday, did you eat any of the following foods: kangaroo or penguin?\n',
                'preamble_sw': 'Jana, ulikula chochote kati ya vyakula vifuatavyo: kangaruu au pengwini?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q13',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Yesterday, did you eat any of the following foods of animal origin: Eggs?\n',
                'preamble_sw': 'Je, jana ulikula yoyote ya vyakula vifuatavyo vya asili ya wanyama: Mayai?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q14',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Cheese?\n',
                'preamble_sw': 'Jibini?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q15',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Yogurt or mala?\n',
                'preamble_sw': 'Mtindi, mala au maziwa lala?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q16',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Sausages, smokies, hot dogs, salami, ham, or dried meat?\n',
                'preamble_sw': 'Sausages, smokies, hot dogs, salami, ham, au nyama kavu?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q17',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Goat, beef, minced beef, mutton, liver or matumbo?\n',
                'preamble_sw': 'Mbuzi, nyama ya ng\'ombe, nyama ya kusaga ya ng\'ombe, nyama ya kondoo, maini au matumbo?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q18',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Pork, rabbit, or camel?\n',
                'preamble_sw': 'Nguruwe, sungura, au ngamia?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q19',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Chicken, duck, turkey, quail, or guinea fowl?\n',
                'preamble_sw': 'Kuku, bata, bata mzinga, kware, au kanga?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q20',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Fish, omena, sardines, canned tuna, or seafood?\n',
                'preamble_sw': 'Samaki, omena, dagaa, samaki wa tuna, au vyakula vya baharini?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q21',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Yesterday, did you eat any of the following: Groundnuts, peanut butter, cashews, almonds, pumpkin seeds, or simsim seed?\n',
                'preamble_sw': 'Je, jana ulikula chakula chochote kati ya vifuatavyo: Karanga, siagi ya karanga, mikorosho, lozi / kungu, mbegu za malenge, au mbega za ufata?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q22',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Crisps, Ringoz, or chevda?\n',
                'preamble_sw': 'Crisps, Ringoz, au Chevda??\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Instructed_response',
            SurveyMenuInterrogator,
            {
                'preamble': 'To show that you are reading the questions, please skip this question.\n',
                'menu_items': [('Yes', 'y'), ('No', 'n'), ('Skip', 's')],
            }
        ),
        (
            'Q23',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Yesterday, did you eat any of the following other foods: Indomie?\n',
                'preamble_sw': 'Je, jana ulikula chakula chochote kati ya vifuatavyo:Indomie?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q24',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Chips, ngumu, mandaazi, samosa, viazi karai or bhajia, or fried chicken?\n',
                'preamble_sw': 'Chips, ngumu, mandaazi, samosa, viazi karai au bhajia, au kuku wa kukaanga?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q25',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Yesterday, did you drink any of the following beverages: Milk, tea with milk, or powdered milk?\n',
                'preamble_sw': 'Je, jana ulikunywa kinywaji chochote kati ya vifuatavyo: Maziwa, chai ya maziwa, au maziwa ya unga?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q26',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Tea with sugar, coffee with sugar, Milo, or drinking chocolate?\n',
                'preamble_sw': 'Chai ikiwa na sukari, kahawa ikiwa na sukari, Milo au cocoa?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q27',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Fruit juice or fruit drinks?\n',
                'preamble_sw': 'Juisi ya matunda au vinywaji vya matunda?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q28',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Soft drinks such as Coca-Cola, Fanta, or Sprite, or energy drinks such as Red Bull?\n',
                'preamble_sw': 'Vinywaji baridi kama vile Coca-Cola, Fanta, au Sprite, au au vinywaji vya kuongeza nguvu kama vile Red Bull?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'Q29',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Yesterday, did you get food from any place like: Kenchic, KFC, Chicken Inn, Burger King, Domino\'s, or other places that serve pizza or burgers\n',
                'preamble_sw': 'Jana, ulipata chakula kutoka sehemu yoyote kama: Kenchic, KFC, Chicken Inn, Burger King, Domino\'s au maeneo mengine ambayo huuza pizza au burger?\n',
                'menu_items_en': [('Yes', 'y'), ('No', 'n')],
                'menu_items_sw': [('Ndio', 'y'), ('Hapana', 'n')],
            }
        ),
        (
            'End',
            SurveyMenuInterrogator,
            {
                'preamble_en': 'Thanks for completing the survey. You will soon receive airtime worth Ksh 100.\n',
                'preamble_sw': 'Asante kwa kukamilisha utafiti. Hivi karibuni utapokea muda wa maongezi wenye thamani ya Sh 100.\n',
                'menu_items_en': [('Thanks', '')],
                'menu_items_sw': [('Asante', '')],
            }
        ),
    ]
    hidden = ['Pre-question', 'Intro', 'Intro_2', 'Intro_3', 'Intro_4', 'Bogus_Item', 'Instructed_response', 'End']

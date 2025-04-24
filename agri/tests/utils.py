import datetime

from agri.models.base import Commodity, Region
from agri.models.messaging import AgriTipSMS
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS

from .factories import CommodityFactory, AgriculturalRegionFactory


class CommodityTestCaseMixin(object):
    """ Consolidate common functionality between Commodity related `TestCase`s.
    """

    def create_commodities(self):
        """ Creates commodity fixture data
        """
        self.maize = CommodityFactory(name='maize', crop=True, gets_market_prices=True)
        self.beans = CommodityFactory(name='beans', crop=True)
        self.carrots = CommodityFactory(name='carrots', crop=True)
        self.bananas = CommodityFactory(name='bananas', crop=True)

        self.cow = CommodityFactory(name='cow', seasonal_livestock=True,
                                    commodity_type=Commodity.LIVESTOCK)
        self.calf = CommodityFactory(name='calf', event_based_livestock=True,
                                     fallback_commodity=self.cow,
                                     variant_of=self.cow,
                                     commodity_type=Commodity.LIVESTOCK)

        self.sheep = CommodityFactory(name='sheep', seasonal_livestock=True,
                                      commodity_type=Commodity.LIVESTOCK)
        self.lamb = CommodityFactory(name='lamb', event_based_livestock=True,
                                     commodity_type=Commodity.LIVESTOCK,
                                     fallback_commodity=self.sheep,
                                     variant_of=self.sheep)

    def create_and_subscribe_customers(self):
        # imported here to prevent circular import
        from customers.tests.factories import CustomerFactory

        # Two customers with identical subscriptions and regions. Should
        # receive the same tips.
        self.one = CustomerFactory(name='one',
                                   agricultural_region__name='The North',
                                   commodity_subscriptions1__commodity=self.maize,
                                   commodity_subscriptions2__commodity=self.cow)
        self.two = CustomerFactory(name='two',
                                   agricultural_region__name='The North',
                                   commodity_subscriptions1__commodity=self.maize,
                                   commodity_subscriptions2__commodity=self.cow)

        # Two customers with subscriptions identical to the above but with a
        # different region. Should receive the same tips as each other but
        # distinct from customers one and two.
        self.three = CustomerFactory(name='three',
                                     agricultural_region__name='The South',
                                     commodity_subscriptions1__commodity=self.maize,
                                     commodity_subscriptions2__commodity=self.cow)
        self.four = CustomerFactory(name='four',
                                    agricultural_region__name='The South',
                                    commodity_subscriptions1__commodity=self.maize,
                                    commodity_subscriptions2__commodity=self.cow)

        # One in The North sharing only one subscription with the above
        self.five = CustomerFactory(name='five',
                                    agricultural_region__name='The North',
                                    commodity_subscriptions1__commodity=self.maize,
                                    commodity_subscriptions2__commodity=self.carrots)

        # One in The North with epoch based livestock
        self.six = CustomerFactory(
            name='six',
            agricultural_region__name='The North',
            commodity_subscriptions1__commodity=self.maize,
            commodity_subscriptions2__commodity=self.lamb,
            commodity_subscriptions2__epoch_date=datetime.date(2015, 5, 1))

        # One in The North with same subscriptions bar different epoch date for
        # livestock subscription
        self.seven = CustomerFactory(
            name='seven',
            agricultural_region__name='The North',
            commodity_subscriptions1__commodity=self.maize,
            commodity_subscriptions2__commodity=self.lamb,
            commodity_subscriptions2__epoch_date=datetime.date(2015, 5, 8))

        # One in The North with two different livestock with epochs
        self.eight = CustomerFactory(
            name='eight',
            agricultural_region__name='The North',
            commodity_subscriptions1__commodity=self.calf,
            commodity_subscriptions1__epoch_date=datetime.date(2015, 4, 15),
            commodity_subscriptions2__commodity=self.lamb,
            commodity_subscriptions2__epoch_date=datetime.date(2015, 4, 1))

        # One in the South with same livestock subscriptions as above. Should
        # receive same tips (despite being in a different region)
        self.nine = CustomerFactory(
            name='nine',
            agricultural_region__name='The South',
            commodity_subscriptions1__commodity=self.calf,
            commodity_subscriptions1__epoch_date=datetime.date(2015, 4, 15),
            commodity_subscriptions2__commodity=self.lamb,
            commodity_subscriptions2__epoch_date=datetime.date(2015, 4, 1))

    def create_regions(self):
        self.north = AgriculturalRegionFactory(name='The North')
        self.south = AgriculturalRegionFactory(name='The South')

    def create_crop_agri_tips(self):
        for commodity in Commodity.objects.filter(commodity_type=Commodity.CROP):
            for region in Region.objects.all():
                for number in range(0, 54):
                    text = "{} {} number {}".format(region, commodity, number)
                    AgriTipSMS.objects.create(commodity=commodity, number=number,
                                              region=region, text=text)

    def create_seasonal_livestock_agri_tips(self):
        for commodity in Commodity.objects.filter(commodity_type=Commodity.LIVESTOCK,
                                                  epoch_description=''):
            for number in range(0, 54):
                text = "{} number {}".format(commodity, number)
                AgriTipSMS.objects.create(commodity=commodity, number=number,
                                          text=text)

    def create_event_base_livestock_agri_tips(self):
        # create event-based livestock agri-tips
        for commodity in (Commodity.objects.filter(commodity_type=Commodity.LIVESTOCK)
                                           .exclude(epoch_description=None)):
            # 10 tips, number -5 to 4
            for number in range(-5, 5):
                text = "{} number {}".format(commodity, number)
                AgriTipSMS.objects.create(commodity=commodity, number=number,
                                          text=text)

    def create_all(self):
        """ Helper function for creating all required model instances for
        testing tip sending.
        """
        self.create_regions()
        self.create_commodities()
        self.create_crop_agri_tips()
        self.create_seasonal_livestock_agri_tips()
        self.create_event_base_livestock_agri_tips()
        self.create_and_subscribe_customers()

    def assertTipSent(self, commodity, tip_number, region=None):
        """
        Asserts that an `OutgoingSMS` exists for the AgriTip corresponding
        to the given commodity and tip number (and optionally region).

        Raises:
            AgriTipSMS.DoesNotExist: When no AgriTipSMS exists corresponding to
                the given commodity and tip number (and optionally region).
        """
        ats = AgriTipSMS.objects.get(
            commodity=commodity,
            number=tip_number,
            region=region
        )

        self.assertEqual(1,
                         OutgoingSMS.objects.filter(message_type=OUTGOING_SMS_TYPE.AGRI_TIP,
                                                    extra__tip_id=ats.id).count(),
                         'No OutgoingSMS for {commodity} tip no. #{tip_number}'.format(
                                commodity=commodity,
                                tip_number=tip_number
                         )
        )

    def assertTipSentToCustomers(self, commodity, tip_number, customers,
                                 region=None):
        """
        Asserts that an `OutgoingSMS` has been sent to the given customers
        for the AgriTip corresponding to the given commodity and tip number.

        Raises:
            AgriTipSMS.DoesNotExist: When no AgriTipSMS exists corresponding to
                the given commodity and tip number.
        """
        ats = AgriTipSMS.objects.get(
            commodity=commodity,
            number=tip_number,
            region=region
        )
        outgoing_sms = OutgoingSMS.objects.filter(message_type=OUTGOING_SMS_TYPE.AGRI_TIP,
                                                  extra__tip_id=ats.id).first()

        # Check that we have an OutgoingSMS
        self.assertIsNotNone(
            outgoing_sms,
            msg='No OutgoingSMS exists for {outgoing_sms}'.format(outgoing_sms=outgoing_sms))

        # Check that the OutgoingSMS has the correct recipients
        self.assertSetEqual(
            set(outgoing_sms.sms_recipient.values_list('recipient__name', flat=True)),
            set(c.name for c in customers),
        )

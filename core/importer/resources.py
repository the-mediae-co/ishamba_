# The syntax of an import is:
# class ModelNameResource(resources.ModelResource):
#     {{csv_column}} = Field(attribute={{model_field}},
#                            widget=ForeignKeyLookupWidget(model={{ForeignKeyedModel}},
#                                                          lookup_field={{foreign_model_field}}))
#
#     class Meta:
#         model = {{model}}
#         fields = {{tuple of csv column names}}
#         import_id_fields = {{tuple of field names which are sufficient to identify an object}}

import json
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from import_export import resources
from import_export.exceptions import ImportExportError
from import_export.fields import Field
from import_export.instance_loaders import ModelInstanceLoader
from import_export.widgets import (BooleanWidget, DecimalWidget,
                                   ForeignKeyWidget, ManyToManyWidget)

from agri.models.base import Commodity
from core.importer.widgets import (DateutilDateTimeWidget, FuzzyLookupWidget, LocationWidget,
                                   PhoneNumbersWidget, PreferredLanguageWidget,
                                   BorderWidget, AgriculturalRegionWidget)
from customers.constants import JOIN_METHODS, STOP_METHODS
from customers.models import (Customer, CustomerPhone,
                              CustomerCategory)
from markets.models import Market, MarketPrice, MarketSubscription
from payments.models import Voucher
from sms.models import SMSRecipient
from tips.models import TipSeries, TipSeriesSubscription
from world.models import Border, BorderLevelName
from world.utils import get_border_for_location
from subscriptions.models import Subscription

from .fields import PhonesField

from logging import getLogger
logger = getLogger(__name__)


class TimestampedBaseResourceMixin(object):
    def before_import(self, dataset, using_transactions, dry_run, *args, **kwargs):
        # Record which user is conducting the import
        self.user = kwargs.get('user', None)


class MarketPriceResource(TimestampedBaseResourceMixin, resources.ModelResource):
    """ A market price record from a M.A.L.F. provided csv file. There are two
        extra fields available which we're ignoring at the moment:
            - Category, e.g. "CEREALS", "LEGUMES"
            - Package, e.g. "Bag", "Ext Bag", "Sm Basket", "Dozen", "Tray"
    """

    date = Field(attribute='date', column_name='Date',
                 widget=DateutilDateTimeWidget())
    commodity = Field(attribute='commodity', column_name='Commodity',
                      widget=FuzzyLookupWidget(model=Commodity,
                                               lookup_field='name'))
    capacity = Field(attribute='amount', column_name='Capacity')
    unit = Field(attribute='unit', column_name='Unit')
    price = Field(attribute='price', column_name='Price')
    market = Field(attribute='market', column_name='Market',
                   widget=FuzzyLookupWidget(model=Market,
                                            lookup_field='name'))

    class Meta:
        model = MarketPrice
        fields = ('date', 'commodity', 'amount', 'price', 'unit', 'market')
        import_id_fields = ('date', 'market', 'commodity')

    def before_save_instance(self, instance, *args, **kwargs):
        super().before_save_instance(instance, *args, **kwargs)
        if instance.unit in ('', None):
            instance.unit = 'unit'
        if instance.amount in ('', None):
            instance.amount = 1
        # To set a different source, we'd most likely write a different class,
        # so it's okay to leave this hardwired for now.
        instance.source = "M.A.L.F."


class VoucherResource(TimestampedBaseResourceMixin, resources.ModelResource):

    class Meta:
        model = Voucher
        fields = ('id', 'created', 'offer', 'number', 'code', 'used_by')


class CustomerInstanceLoaderClass(ModelInstanceLoader):
    """
    A custom CustomerInstanceLoader to use with CustomerImportResource. This is
    needed because we identify customers by their phone number, which is stored
    in a foreign key field. Also, the 'phones' import column can contain multiple
    phone numbers, so we need to search all to find a matching customer.
    """
    def get_instance(self, row):
        try:
            params = {}
            for key in self.resource.get_import_id_fields():
                field = self.resource.fields[key]
                params[field.attribute] = field.clean(row)
            if params:
                return self.get_queryset().get(**params)
            else:
                return None
        except self.resource._meta.model.DoesNotExist:
            return None
        except self.resource._meta.model.MultipleObjectsReturned:
            raise ImportExportError(f"The phone numbers belong to multiple customers")


class CustomerImportResource(TimestampedBaseResourceMixin, resources.ModelResource):
    name = Field(attribute='name', default='')
    sex = Field(attribute='sex', default='')
    phones = PhonesField(attribute='phones__number__in',
                         column_name='phones',
                         widget=PhoneNumbersWidget(model=CustomerPhone, field='number',))
    village = Field(attribute='village', default='')

    border0 = Field(attribute='border0', widget=BorderWidget(0))
    border1 = Field(attribute='border1', widget=BorderWidget(1), default=None)
    border2 = Field(attribute='border2', widget=BorderWidget(2), default=None)
    border3 = Field(attribute='border3', widget=BorderWidget(3), default=None)

    agricultural_region = Field(attribute='agricultural_region', widget=AgriculturalRegionWidget())
    preferred_language = Field(attribute='preferred_language', widget=PreferredLanguageWidget())
    farm_size = Field(attribute='farm_size', widget=DecimalWidget())
    notes = Field(attribute='notes', default='')
    location = Field(attribute='location', widget=LocationWidget())

    # M2M fields
    commodities = Field(attribute='commodities',
                        widget=ManyToManyWidget(model=Commodity,
                                                field='name',
                                                ))
    categories = Field(attribute='categories',
                       widget=ManyToManyWidget(model=CustomerCategory,
                                               field='name',))

    class Meta:
        model = Customer
        skip_unchanged = True
        report_skipped = True
        exclude = ('id',)
        fields = ('name', 'sex', 'phones', 'village',
                  'border0', 'border1', 'border2', 'border3', 'agricultural_region',
                  'preferred_language', 'farm_size', 'notes', 'location',
                  'commodities', 'categories')
        import_id_fields = ('phones',)
        instance_loader_class = CustomerInstanceLoaderClass

    def before_import(self, dataset, using_transactions, dry_run, *args, **kwargs):
        # Before conducting the import, we want to check the administrative boundary
        # columns since the operator may have used column names for different countries.
        # E.g. Country, County, Subcounty, Ward in Kenya or Country, Region, District, County in Uganda

        # But first, strip any whitespace at the ends of each header
        for i, h in enumerate(dataset.headers):
            dataset.headers[i] = h.strip()

        super().before_import(dataset, using_transactions, dry_run, *args, **kwargs)

        # Check if there are any unrecognized columns and highlight those as errors.
        all_names = list(map(lambda x: x.lower(), BorderLevelName.objects.values_list('name', flat=True)))
        all_names.extend(list(map(lambda x: x.lower(), self.Meta.fields)))
        errors = []
        for h in dataset.headers:
            if h.lower() not in all_names:
                errors.append(_(f'Unrecognized column: {h}'))
        if errors:
            raise ValidationError(errors)

        # Regarding border column recognition, first check if the generic names are used. If so, no need
        # to change anything.
        # if all(map(lambda x: x in dataset.headers, ['border0', 'border1', 'border2', 'border3'])):
        #     return
        # Alternatively, instead of border0, a column header of country can be clearer
        # if all(map(lambda x: x in dataset.headers, ['country', 'border1', 'border2', 'border3'])):
        #     return

        # Search for country specific column names
        country_names = Border.objects.filter(level=0).values_list('name', flat=True)
        found_country = False
        for country_name in country_names:
            # Look up administrative border level names, limiting the list to 4
            border_names = [x.lower() for x in BorderLevelName.objects.filter(country=country_name).order_by('level').values_list('name', flat=True)[:4]]
            # If all of the border level names are in the headers, then we identified the right country
            if all(map(lambda x: x in dataset.headers, border_names)):
                logger.debug(f"IMPORT: Country {country_name} has been identified by headers {border_names}")
                found_country = True
                for level in range(4):
                    level_name = BorderLevelName.objects.get(country=country_name, level=level).name
                    attr_name = f"border{level}"
                    self.fields.get(attr_name).column_name = level_name.lower()  # column_name maps to the user visible column header name
                    self.fields.get(attr_name).widget.country_name = country_name
                    self.fields.get(attr_name).widget.level_name = level_name
                break

        if not found_country:
            # If we didn't determine the country by the column header names, search the rows for a country name
            error_msg = _("Cannot determine import Country. Please either name the column headers "
                          "with the corresponding administrative border names for the country or "
                          "use 'border0' for Country, 'border1' for County, 'border2' for Subcounty, etc.")
            country_name = None
            lower_headers = [x.lower() for x in dataset.headers]
            keyname = None
            for option in ('border0', 'country'):
                if option in lower_headers:
                    index = lower_headers.index(option)
                    keyname = dataset.headers[index]
                    break

            if not keyname:
                raise ValidationError(error_msg)

            rows = json.loads(dataset.json)
            for row in rows:
                # Try to find a country name in the rows of the sheet
                country_name_candidate = row.get(keyname)
                if found_country and country_name_candidate and country_name_candidate.lower() != country_name.lower():
                    # If the sheet has multiple countries, raise an error
                    raise ValidationError(f"Detected multiple countries in the sheet. Please only import "
                                          f"customers from one country per sheet.")
                if country_name_candidate and country_name_candidate.lower() in ('kenya', 'uganda', 'zambia'):
                    found_country = True
                    country_name = country_name_candidate.title()

            # Finally, set all of the input BorderWidget values to use the country that we found
            for level in range(4):
                level_name = BorderLevelName.objects.get(country=country_name, level=level).name
                attr_name = f"border{level}"
                self.fields.get(attr_name).column_name = level_name.lower()  # column_name maps to the user visible column header name
                self.fields.get(attr_name).widget.country_name = country_name
                self.fields.get(attr_name).widget.level_name = level_name

    def after_import(self, dataset, result, using_transactions, dry_run, **kwargs):
        for index in range(len(result.diff_headers)):
            header = result.diff_headers[index]
            if self.fields.get(header) is not None and self.fields.get(header).column_name != header:
                # Show the administrative boundary names that were used in the import sheet
                # instead of the generic 'border0', 'border1', etc.
                result.diff_headers[index] = self.fields.get(header).column_name

    def skip_row(self, instance, original):
        """
        Returns ``True`` if ``row`` importing should be skipped.
        Default implementation returns ``False`` unless skip_unchanged == True.
        Override this method to handle skipping rows meeting certain conditions.
        """
        should_skip = super().skip_row(instance, original)
        if should_skip:
            return True
        if original.pk and not settings.CUSTOMER_IMPORT_PERMIT_UPDATE:
            return True
        return False

    def before_save_instance(self, instance, using_transactions, dry_run):
        super().before_save_instance(instance, using_transactions, dry_run)
        if dry_run:
            try:
                instance.clean()
                phones_field = self.fields.get('phones')
                if not phones_field.phones:
                    raise ImportExportError(_("At least one phone number is required for each customer"))
            except ValidationError as e:
                raise ImportExportError(e.message)
        else:
            instance.is_registered = True
            instance.has_requested_stop = False
            if instance.location:
                if not instance.border3:
                    instance.border3 = get_border_for_location(instance.location, 3)
                if not instance.border2:
                    instance.border2 = instance.border3.parent
                if not instance.border1:
                    instance.border1 = instance.border3.parent
            else:
                # If no GPS location was set, calculate the center of the administrative boundary
                if instance.border3:
                    instance.location = instance.border3.border.centroid
                # Don't set location based on border0 or border0 since they are too large to be accurate

            # If the has_requested_stop flag was set, record the method
            if instance.has_requested_stop:
                instance.stop_method = STOP_METHODS.IMPORT
                instance.stop_date = now().date()

            # If this is a newly created customer
            instance.join_method = JOIN_METHODS.IMPORT

    def after_save_instance(self, instance, using_transactions, dry_run):
        if not dry_run:
            # Create CustomerPhone objects for the newly created customer object
            phones_field = self.fields.get('phones')
            if phones_field.phones:
                phones = phones_field.get_value(instance)
                for idx, phone_str in enumerate(phones):
                    # If the CustomerPhone object already existed, don't create a duplicate.
                    # This should never happen since we check for duplicates in PhoneNumbersWidget.clean()
                    CustomerPhone.objects.get_or_create(number=phone_str, is_main=(idx == 0), customer=instance)

    # def save_m2m(self, obj, data, using_transactions, dry_run):
    #     super().save_m2m(obj, data, using_transactions, dry_run)
    #     self.after_save_m2m(obj, data, dry_run)

    # def after_save_m2m(self, obj, data, dry_run):
    #     """ This is to save_m2m as after_save_instance is to save_instance.
    #     """
    #     if not dry_run:
    #         for commodity in obj.commodities.all():
    #             send_market_prices = True
    #             if commodity.commodity_type == Commodity.LIVESTOCK:
    #                 send_market_prices = False
    #             defaults = {
    #                 'send_market_prices': send_market_prices,
    #             }
    #             if commodity.is_event_based:
    #                 defaults['epoch_date'] = now().date()
    #             cs, created = CommoditySubscription.objects.get_or_create(
    #                 subscriber=obj,
    #                 commodity=commodity,
    #                 defaults=defaults
    #             )


class CustomerExportResource(TimestampedBaseResourceMixin, resources.ModelResource):
    """
    No `commodity_subscriptions` field. Instead, all commodities listed will
    be given commodity subscriptions in post-processing.
    """
    id = Field(attribute='id', default='')
    name = Field(attribute='name', default='')
    sex = Field(attribute='sex', default='')
    village = Field(attribute='village', default='')

    border0 = Field(attribute='border0', widget=BorderWidget(0))
    border1 = Field(attribute='border1', widget=BorderWidget(1), default=None)
    border2 = Field(attribute='border2', widget=BorderWidget(2), default=None)
    border3 = Field(attribute='border3', widget=BorderWidget(3), default=None)

    agricultural_region = Field(attribute='agricultural_region', widget=AgriculturalRegionWidget())
    preferred_language = Field(attribute='preferred_language', widget=PreferredLanguageWidget())
    farm_size = Field(attribute='farm_size', widget=DecimalWidget())
    notes = Field(attribute='notes', default='')
    is_registered = Field(attribute='is_registered', widget=BooleanWidget(), default=False)
    has_requested_stop = Field(attribute='has_requested_stop', widget=BooleanWidget(), default=False)

    # M2M fields
    commodities = Field(attribute='commodities',
                        widget=ManyToManyWidget(model=Commodity,
                                                # field='name',
                                                # separator=','
                                                ))
    categories = Field(attribute='categories',
                       widget=ManyToManyWidget(model=CustomerCategory))

    should_receive_messages = Field(readonly=True)
    received_message_count = Field(readonly=True)
    end_date_of_last_subscription = Field(readonly=True)

    class Meta:
        model = Customer
        fields = ('id', 'name', 'sex', 'village', 'border3',
                  'border2', 'border1', 'border0', 'agricultural_region',
                  'preferred_language', 'farm_size', 'notes', 'is_registered',
                  'has_requested_stop', 'commodities', 'categories',
                  'should_receive_messages', 'received_message_count',
                  'end_date_of_last_subscription')

    def dehydrate_is_registered(self, instance):
        return instance.is_registered

    def dehydrate_has_requested_stop(self, instance):
        return instance.has_requested_stop

    def dehydrate_commodities(self, instance):
        if hasattr(instance, 'id') and instance.id is not None:
            return ','.join(instance.commodities.values_list('name', flat=True))
        return None

    def dehydrate_categories(self, instance):
        if hasattr(instance, 'id') and instance.id is not None:
            return ','.join(instance.categories.values_list('name', flat=True))
        return None

    def dehydrate_should_receive_messages(self, instance):
        return instance.should_receive_messages

    def dehydrate_received_message_count(self, instance):
        return SMSRecipient.objects.filter(recipient=instance).count()

    def dehydrate_end_date_of_last_subscription(self, instance):
        try:
            subscription = instance.subscriptions.latest('end_date')
        except Subscription.DoesNotExist:
            return ""
        else:
            return subscription.end_date


class MarketSubscriptionResource(TimestampedBaseResourceMixin, resources.ModelResource):
    customer = Field(
        attribute="customer",
        widget=ForeignKeyWidget(Customer),
        column_name="customer",
    )
    market = Field(
        attribute="market", widget=ForeignKeyWidget(Market, field="name"), column_name="market"
    )
    backup = Field(
        attribute="backup",
        widget=ForeignKeyWidget(Market, field="name"),
        column_name="backup",
    )
    commodity = Field(
        attribute="commodity",
        widget=ForeignKeyWidget( model=Commodity, field="name",),
        column_name="commodity",
    )

    class Meta:
        model = MarketSubscription
        fields = ("customer", "market", "backup", "commodity")
        import_id_fields = ("customer", "market", "backup", "commodity")

    def before_save_instance(self, instance, using_transactions, dry_run):
        super().before_save_instance(instance, using_transactions, dry_run)
        if dry_run:
            try:
                instance.clean()
            except ValidationError as e:
                raise ImportExportError(e.message)


class TipSeriesSubscriptionResource(TimestampedBaseResourceMixin, resources.ModelResource):
    customer = Field(attribute='customer', widget=ForeignKeyWidget(Customer, 'customer__phones__number'),
                     column_name='phones')
    series = Field(attribute='series', widget=ForeignKeyWidget(TipSeries), column_name='series')
    start = Field(attribute='start', widget=DateutilDateTimeWidget(), column_name='start')

    class Meta:
        model = TipSeriesSubscription
        fields = ('customer', 'series', 'start')
        import_id_fields = ('customer', 'series')

    def before_save_instance(self, instance, using_transactions, dry_run):
        super().before_save_instance(instance, using_transactions, dry_run)
        if dry_run:
            try:
                instance.clean()
            except ValidationError as e:
                raise ImportExportError(e.message)

import phonenumbers
from django.contrib.auth import get_user_model

from rest_framework import serializers

from calls.models import Call
from core.logger import log
from customers.models import Customer, CustomerPhone
from markets.models import MarketPrice
from sms.constants import OUTGOING_SMS_TYPE, SMS_TYPE_ICON_MAP
from sms.models import IncomingSMS, SMSRecipient, OutgoingSMS
from weather.models import ForecastDay
from world.models import Border
from world.utils import get_country_for_phone

User = get_user_model()


class OutgoingSMSSerializer(serializers.ModelSerializer):
    sms_type = "Outgoing SMS"
    message_type_icon = serializers.SerializerMethodField()
    message_type_description = serializers.SerializerMethodField()

    class Meta:
        model = OutgoingSMS
        fields = ('text', 'time_sent', 'message_type', 'message_type_icon', 'message_type_description')

    def get_message_type_icon(self, obj: OutgoingSMS):
        return SMS_TYPE_ICON_MAP.get(obj.message_type)

    def get_message_type_description(self, obj: OutgoingSMS):
        return obj.get_message_type_display()


class IncomingSMSSerializer(serializers.ModelSerializer):
    sms_type = "Incoming SMS"

    class Meta:
        model = IncomingSMS
        fields = ('created', 'text')


class SMSRecipientSerializer(serializers.ModelSerializer):

    class Meta:
        model = SMSRecipient
        fields = ('created', 'message')


class PreviousCallSerializer(serializers.ModelSerializer):
    cco = serializers.StringRelatedField()

    class Meta:
        model = Call
        fields = ('created_on', 'notes', 'issue_resolved', 'cco')


class MarketSubscriptionMixin(object):
    def get_market_subscriptions(self, obj):
        markets = []
        subscriptions = obj.market_subscriptions.values_list('market__pk',
                                                             'market__name',
                                                             'backup__pk',
                                                             'backup__name')
        for subscription in subscriptions:
            main_pk, main_name, backup_pk, backup_name = subscription
            markets.append({'id': main_pk, 'name': main_name})
            if backup_pk:
                markets.append({'id': backup_pk, 'name': backup_name})
        return markets


class TipSubscriptionMixin(object):
    def get_tip_subscriptions(self, customer):
        if not customer:
            return []

        output = []
        subscriptions = (
            customer.tip_subscriptions
                    .filter(ended=False)
                    .values_list(
                        'series__pk',
                        'series__name',
                        'start',
                        'ended',
            )
        )
        for tss in subscriptions:
            pk, name, start, ended = tss
            output.append({'id': pk, 'name': name, 'start': start, 'ended': ended})
        return output


class SimpleCustomerSerializer(MarketSubscriptionMixin, TipSubscriptionMixin,
                               serializers.ModelSerializer):
    agricultural_region = serializers.StringRelatedField()
    commodities = serializers.StringRelatedField(many=True)
    tip_subscriptions = serializers.SerializerMethodField()
    market_subscriptions = serializers.SerializerMethodField()

    # Data is posted to us using 'phone' but our model has a foreign key to
    # a model named 'phones'. So this field is created as write_only so that
    # the REST framework does not try to validate it against the model.
    # https://www.django-rest-framework.org/api-guide/fields/#write_only
    phone = serializers.CharField(max_length=50, write_only=True)

    class Meta:
        model = Customer
        depth = 1
        fields = ('name', 'phone', 'commodities', 'tip_subscriptions',
                  'market_subscriptions', 'preferred_language', 'notes',
                  'agricultural_region')

    def validate_phone(self, value):
        try:
            phone = phonenumbers.parse(value)
        except phonenumbers.phonenumberutil.NumberParseException:
            raise serializers.ValidationError('Invalid phone number.')

        if not phonenumbers.is_valid_number(phone):
            raise serializers.ValidationError('Invalid phone number.')

        try:
            # We only have countries where we operate in the BorderLevelName database
            country = get_country_for_phone(phone)
        except ValueError:
            raise serializers.ValidationError('Not a country that we operate in.')

        try:
            # We do not allow duplicate phone numbers
            existing = CustomerPhone.objects.get(number=phone)
            # If no exception is raised, we have a duplicate
            raise serializers.ValidationError('That phone number is already used by an existing customer.')
        except CustomerPhone.DoesNotExist:
            return phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)

    def create(self, validated_data):
        number = validated_data.pop('phone')
        customer = Customer.objects.create(**validated_data)
        phone = CustomerPhone.objects.create(
            number=number,
            is_main=True,
            customer=customer,
        )
        return customer


class CustomerSerializer(MarketSubscriptionMixin, TipSubscriptionMixin, serializers.ModelSerializer):
    region = serializers.StringRelatedField()
    commodities = serializers.StringRelatedField(many=True)
    tip_subscriptions = serializers.SerializerMethodField()
    market_subscriptions = serializers.SerializerMethodField()
    call_set = serializers.SerializerMethodField()
    smsrecipient_set = SMSRecipientSerializer(many=True)
    location = serializers.SerializerMethodField()
    weather_area = serializers.PrimaryKeyRelatedField(read_only=True)
    preferred_language = serializers.CharField(source='get_preferred_language_display')
    border0 = serializers.PrimaryKeyRelatedField(allow_null=True, queryset=Border.objects.filter(level=0))
    border1 = serializers.PrimaryKeyRelatedField(allow_null=True, queryset=Border.objects.filter(level=1))
    border2 = serializers.PrimaryKeyRelatedField(allow_null=True, queryset=Border.objects.filter(level=2))
    border3 = serializers.PrimaryKeyRelatedField(allow_null=True, queryset=Border.objects.filter(level=3))
    sex = serializers.CharField()

    class Meta:
        model = Customer
        depth = 1
        fields = ('name', 'commodities', 'tip_subscriptions',
                  'market_subscriptions', 'preferred_language', 'notes',
                  'region', 'call_set', 'smsrecipient_set', 'weather_area',
                  'location', 'id', 'border0', 'border1', 'border2', 'border3', 'sex')

    def get_location(self, obj):
        try:
            return {'x': obj.location.x,
                    'y': obj.location.y}
        except AttributeError:
            return {}

    # List the calls in descending order by date (most recent first)
    def get_call_set(self, instance):
        calls = instance.call_set.order_by('-created_on')
        return PreviousCallSerializer(calls, many=True).data


class ForecastDaySerializer(serializers.ModelSerializer):
    conditions = serializers.SerializerMethodField()

    class Meta:
        model = ForecastDay
        fields = ('target_date', 'conditions',)

    def get_conditions(self, obj):
        return obj.json['conditions'][0]


class CallSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    cco = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Call
        depth = 1
        fields = ('id', 'cco', 'provided_id', 'caller_number', 'notes',
                  'issue_resolved', 'destination_number', 'customer',
                  'is_active', 'connected', 'created_on', 'connected_on',
                  'hanged_on', 'previous_calls_number', )


class SimpleCallSerializer(serializers.ModelSerializer):
    customer = SimpleCustomerSerializer(read_only=True)
    cco = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Call
        depth = 1
        fields = ('id', 'cco', 'provided_id', 'caller_number',
                  'destination_number', 'customer', 'is_active', 'connected',
                  'created_on', 'connected_on', 'hanged_on',
                  'previous_calls_number',)


class CCOCallSerializer(serializers.ModelSerializer):
    connected_call = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'connected_call', )

    def get_connected_call(self, obj):
        try:
            call = Call.objects.connected().get(cco=obj)
        except Call.DoesNotExist:
            return None
        except Call.MultipleObjectsReturned:
            log.error("Multiple calls connected to the same CCO simultaneously.")
        else:
            return CallSerializer(call).data


class MarketPriceSerializer(serializers.ModelSerializer):
    market = serializers.StringRelatedField()
    commodity = serializers.StringRelatedField()

    class Meta:
        model = MarketPrice
        fields = ('id', 'market', 'commodity', 'date', 'price', 'source',
                  'amount', 'unit')

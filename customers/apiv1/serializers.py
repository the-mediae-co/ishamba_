import json
import traceback
import phonenumbers

from django.conf import settings
from django.core.mail import EmailMessage

from rest_framework import serializers
from rest_framework.utils import model_meta

from world.utils import get_country_for_phone

import sentry_sdk

from customers.models import Customer, CustomerPhone, CustomerQuestionAnswer
from subscriptions.models import SubscriptionType, Subscription


class TimestampedBaseSerializer(serializers.ModelSerializer):

    def create(self, validated_data):
        ModelClass = self.Meta.model
        info = model_meta.get_field_info(ModelClass)
        many_to_many = {}
        for field_name, relation_info in info.relations.items():
            if relation_info.to_many and (field_name in validated_data):
                many_to_many[field_name] = validated_data.pop(field_name)

        try:
            instance = ModelClass(**validated_data)
            user = self.context['request'].user
            instance.save(user=user)
        except TypeError:
            tb = traceback.format_exc()
            msg = (
                'Got a `TypeError` when calling `%s.objects.create()`. '
                'This may be because you have a writable field on the '
                'serializer class that is not a valid argument to '
                '`%s.objects.create()`. You may need to make the field '
                'read-only, or override the %s.create() method to handle '
                'this correctly.\nOriginal exception was:\n %s' %
                (
                    ModelClass.__name__,
                    ModelClass.__name__,
                    self.__class__.__name__,
                    tb
                )
            )
            raise TypeError(msg)

        # Save many-to-many relationships after the instance is created.
        if many_to_many:
            for field_name, value in many_to_many.items():
                field = getattr(instance, field_name)
                field.set(value)

        return instance


class CustomerPhoneRelatedField(serializers.RelatedField):

    default_error_messages = {
        'does_not_exist': "Customer with phone '{number}' does not exist",
    }

    def get_queryset(self):
        return CustomerPhone.objects.all()

    def to_internal_value(self, data):
        try:
            return Customer.objects.get(phones__number=data)
        except CustomerPhone.DoesNotExist:
            self.fail('does_not_exist', number=data)

    def to_representation(self, value):
        return str(value.number)


class SubscriptionTypeField(serializers.RelatedField):

    default_error_messages = {
        'does_not_exist': "Subscription type '{name}' does not exist",
    }

    def get_queryset(self):
        return Subscription.objects.all()

    def to_internal_value(self, data):
        try:
            return SubscriptionType.objects.get(name=data)
        except SubscriptionType.DoesNotExist:
            self.fail('does_not_exist', name=data)

    def to_representation(self, value):
        return value.name


class TipSeriesSubscriptionField(serializers.RelatedField):

    def to_representation(self, value):
        return value.series.name


class CustomerJoinSerializer(serializers.Serializer):
    """
    A serializer for use from the ishamba web site, where only a phone number is passed
    """
    # Data is posted to us using 'phone' but our model has a foreign key to
    # a model named 'phones'. So this field is created as write_only so that
    # the REST framework does not try to validate it against the model.
    # https://www.django-rest-framework.org/api-guide/fields/#write_only
    phone = serializers.CharField(max_length=50, write_only=True)

    class Meta:
        fields = ['phone']

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
            return value

    def create(self, validated_data):
        number = validated_data.pop('phone')
        customer = Customer.objects.create(**validated_data)
        phone = CustomerPhone.objects.create(
            number=number,
            is_main=True,
            customer=customer,
        )
        return customer


class CustomerWithNameJoinSerializer(CustomerJoinSerializer):
    """ A serializer for use from ishamba.com where a phone number and name are passed"""
    name = serializers.CharField(max_length=120)

    class Meta:
        fields = ['phone', 'name']


class ChatbotSerializer(serializers.Serializer):
    """ A serializer for use from budgetmkononi.com where a phone number, name and chatbot message are passed"""
    # NOTE: not used
    name = serializers.CharField(max_length=120, required=False, default='')
    phone = serializers.CharField(max_length=50, write_only=True)
    message = serializers.CharField(max_length=1024)
    email = serializers.CharField(required=False, default='')
    preferred_language = serializers.CharField(required=False, default='en')

    def create(self, validated_data):
        sentry_sdk.capture_message(f"Inside ChatbotSerializer.create({validated_data})")
        number = validated_data.pop('phone')
        name = validated_data.pop('name')
        message = validated_data.pop('message')
        email = validated_data.pop('email')
        preferred_language = validated_data.pop('preferred_language')

        received = json.dumps({
            'number': number,
            'name': name,
            'message': message,
            'email': email,
            'preferred_language': preferred_language,
        })

        sentry_sdk.capture_message(f"Chatbot API received: {received}")
        email = EmailMessage(
            subject="[iShamba] Chatbot test",
            body=f"iShamba received the following data:\n\t{received}\n",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=['elizabeth@mediae.org'],
            reply_to='elizabeth@mediae.org',
        )
        email.send(fail_silently=False)


class CustomerSerializer(TimestampedBaseSerializer):

    cooperative = serializers.SerializerMethodField()
    commodities = serializers.StringRelatedField(many=True, read_only=True)
    border0 = serializers.StringRelatedField()

    class Meta:
        model = Customer
        fields = ('name', 'phones', 'sex', 'border0', 'commodities', 'cooperative')

    def get_cooperative(self, obj):
        # This field is tied to the specific question text
        try:
            return obj.answers.get(question__text='Cooperative').text or None
        except CustomerQuestionAnswer.DoesNotExist:
            return None


class SubscriptionSerializer(TimestampedBaseSerializer):
    customer = CustomerPhoneRelatedField()
    type = SubscriptionTypeField()

    class Meta:
        model = Subscription
        fields = ('customer', 'start_date', 'end_date', 'type', 'extra')

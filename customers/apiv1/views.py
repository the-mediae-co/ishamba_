import json

from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import ValidationError as RestValidationError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.utils.translation import gettext_lazy as _
from customers.constants import JOIN_METHODS

from world.utils import get_country_for_phone

from tasks.models import Task, TaskUpdate

from ..models import CustomerCategory, Customer, get_or_create_customer_by_phone
from . import serializers
from .permissions import ChatbotTestingPermission

import sentry_sdk


class CustomerJoinView(CreateAPIView):
    """
    API endpoint for the creation of new (unregistered) Customers.
    """

    permission_classes = (AllowAny,)

    # Instead of instantiating a static serializer, we override
    # get_serializer_class so that we can dynamically instantiate
    # the right serializer based on the data passed in.
    def get_serializer_class(self):
        """ An authenticated user looking at their own user object gets more data """
        if 'name' in self.request.data:
            return serializers.CustomerWithNameJoinSerializer
        return serializers.CustomerJoinSerializer

    def perform_create(self, serializer):
        customer = serializer.save()
        # If we get here, the phone number will have been validated, as well as the associated country
        if customer and not customer.border0:
            if any([customer.border1, customer.border2, customer.border3]):
                # Set the customer's other administrative boundaries based on what we have
                if customer.border3 and not customer.border2:
                    customer.border2 = customer.border3.parent
                if customer.border2 and not customer.border1:
                    customer.border1 = customer.border2.parent
                if customer.border1 and not customer.border0:
                    customer.border0 = customer.border1.parent
            elif customer.main_phone:
                # Guess the customer's country (border0) by their phone number
                try:
                    country = get_country_for_phone(customer.main_phone)
                    customer.border0 = country
                except ValueError:
                    customer.delete()  # Remove the invalid customer
                    raise RestValidationError(_('Not a country that we operate in.'))
        customer.join_method = JOIN_METHODS.WEB
        customer.save(update_fields=['join_method', 'border0', 'border1', 'border2', 'border3'])
        customer.enroll()


class ChatbotTestingView(CreateAPIView):
    """
    API endpoint for testing the budget mkononi chatbot feature.
    """

    permission_classes = (ChatbotTestingPermission,)
    http_method_names = ['post']

    if not settings.DEBUG:
        valid_server_id = '52.208.21.31'
    else:
        valid_server_id = '127.0.0.1'

    def post(self, request, *args, **kwargs):
        number = request.data.get('phone')
        name = request.data.get('name', '')
        message = request.data.get('message')
        email = request.data.get('email', '')
        preferred_language = request.data.get('preferred_language', 'en')

        if (
            request.META.get('REMOTE_ADDR') == self.valid_server_id
            or request.META.get('X_FORWARDED_FOR') == self.valid_server_id
            or request.META.get('HTTP_X_REAL_IP') == self.valid_server_id
        ):
            customer, customer_created = get_or_create_customer_by_phone(
                number,
                JOIN_METHODS.BM_CHATBOT
            )
            if not customer.name:
                customer.name = name
                customer.save(update_fields=['name'])
            if not customer.border0:
                try:
                    customer.border0 = get_country_for_phone(number)
                    customer.save()
                except ValueError as e:
                    pass

            description = f'Reply to BM-chatbot message: ' + message
            task = Task.objects.create(
                customer=customer,
                description=description,
                source=customer,
                priority='high'
            )
            TaskUpdate.objects.create(
                task=task,
                status=Task.STATUS.new,
            )
            # if False and customer_created:
            #     self.respond_to_join()
            # sentry_sdk.capture_message(f"BM Task Created: {task}")
        else:
            # Testing
            received = json.dumps({
                'number': number,
                'name': name,
                'message': message,
                'email': email,
                'preferred_language': preferred_language,
            })
            # sentry_sdk.capture_message(f"ChatbotTestingView received: {received}")
            email = EmailMessage(
                subject="[iShamba] Chatbot test",
                body=f"iShamba received the following data:\n\t{received}\n",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=['elizabeth@mediae.org'],
                reply_to=['elizabeth@mediae.org'],
            )
            email.send(fail_silently=True)

        return Response({'answer': f'Thanks for your message {name}. Our experts will send you a response on your phone number {number} soon.'}, status=201)


class CustomerCreateView(CreateAPIView):

    serializer_class = serializers.CustomerSerializer
    permission_classes = (IsAuthenticated,)

    def send_welcome_sms(self, customer):
        customer.send_welcome_sms(context={'username': self.username})

    def add_customer_to_category(self, customer):
        category, created = CustomerCategory.objects.get_or_create(name=self.username)
        customer.categories.add(category)

    def create_welcome_task(self, customer):
        return customer.tasks.create(
            customer=customer,
            description="Enroll new customer added by {username}".format(username=self.username),
            source=customer,
        )

    def perform_create(self, serializer):
        customer = serializer.save()
        # If we get here, the phone number will have been validated, as well as the associated country
        if customer and customer.main_phone and not customer.border0:
            # Guess the customer's country (border0) by their phone number
            try:
                country = get_country_for_phone(customer.main_phone)
                customer.border0 = country
            except ValueError:
                raise ValidationError(_('Not a country that we operate in.'))
        customer.join_method = JOIN_METHODS.STAFF
        customer.save(update_fields=['join_method', 'border0'])
        self.username = self.request.user.username
        self.send_welcome_sms(customer)
        self.add_customer_to_category(customer)
        self.create_welcome_task(customer)
        sentry_sdk.capture_message(f"CustomerCreateView API created a new customer: {customer.id}.")  # Create a Sentry message


# class CustomerDetailView(RetrieveAPIView):
#
#     queryset = Customer.objects.all()
#     serializer_class = serializers.CustomerSerializer
#     permission_classes = (IsAuthenticated,)
#     lookup_field = 'phones__number'


class SubscriptionCreateView(CreateAPIView):

    serializer_class = serializers.SubscriptionSerializer
    permission_classes = (IsAuthenticated,)

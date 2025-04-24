from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from customers.models import Customer, CustomerQuestion, CustomerQuestionAnswer


def handle_customer_post_save(sender, instance, created, **kwargs):
    if created and not instance.digifarm_farmer_id:
        from subscriptions.models import Subscription, SubscriptionType, SubscriptionAllowance
        # Just in case the default subscription does not exist
        sub_type, type_created = SubscriptionType.objects.get_or_create(
            name='Free',
            defaults=settings.CUSTOMERS_SUBSCRIPTION_DEFAULTS
        )
        # Using get_or_create to guard against multiple signals
        Subscription.objects.get_or_create(customer=instance, type=sub_type)
        # If the type has just been created, add some allowances
        if type_created:
            for code, allowance in settings.CUSTOMERS_SUBSCRIPTION_DEFAULT_ALLOWANCES.items():
                SubscriptionAllowance.objects.get_or_create(code=code, type=sub_type, allowance=allowance)

        # Create empty answers when a customer is first created
        to_create = []
        for question_pk in CustomerQuestion.objects.values_list('pk', flat=True):
            to_create.append(
                CustomerQuestionAnswer(
                    question_id=question_pk,
                    customer_id=instance.pk,
                    text=''
                )
            )
        CustomerQuestionAnswer.objects.bulk_create(to_create, ignore_conflicts=True)

    # If the customer requested stop, stop the subscriptions as well.
    if instance.should_receive_messages is False:
        instance.tip_subscriptions.update(ended=True)


@receiver(post_save, sender=CustomerQuestion)
def handle_customer_question(sender, instance, created, **kwargs):
    """
    Handles creating empty answers to new questions.
    The empty answers are needed to sort an issue when ordering and
    validating the answer formsets.
    """
    if created:
        with_answers = Customer.objects.exclude(answers=None)
        to_create = []
        for customer_pk in with_answers.values_list('pk', flat=True):
            to_create.append(
                CustomerQuestionAnswer(
                    question_id=instance.pk,
                    customer_id=customer_pk,
                    text=''
                )
            )
        CustomerQuestionAnswer.objects.bulk_create(to_create, ignore_conflicts=True)

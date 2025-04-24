from collections import defaultdict

import sentry_sdk
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from core.constants import LANGUAGES

from gateways import SMSGateway

from core.models import TimestampedBase
from customers.models import Customer
from sms import constants, utils

__all__ = ['SMSResponseKeyword', 'SMSResponseTemplate', 'SMSResponseTranslation']

from sms.constants import MAX_SMS_PER_MESSAGE


class SMSResponseKeyword(TimestampedBase):
    """
    Enables the creation of keywords to match against `IncomingSMS` and respond
    with an automated message.
    """
    keyword = models.CharField(
        _('keyword'),
        max_length=160,
        unique=True,
        db_index=True,
        help_text=_("This will match the whole message case-insensitively, "
                    "after surrounding punctuation and whitespace has been stripped.")
    )

    is_active = models.BooleanField('is_active', default=True)

    # responses: SMSResponseTemplate has a ManyToMany field called keywords
    # that has a related_name to this class called responses

    class Meta:
        verbose_name = "SMS response keyword"

    def __str__(self):
        return self.keyword

    def clean_fields(self, exclude=None):
        """
        Implements validation to ensure keywords don't contain boundary
        punctuation and do not conflict with the inbuilt keywords.
        """
        errors = defaultdict(list)

        # TODO: prevent keywords from being added to overlapping countries

        try:
            super().clean_fields(exclude)
        except ValidationError as e:
            errors.update(e.message_dict)

        # Ensure we don't have any boundary punctuation that will be stripped
        # when checking later
        stripped = self.keyword.strip(constants.GSM_WHITELIST_PUNCTUATION)
        if self.keyword != stripped:
            msg = _(
                "Incoming messages are stripped of boundary punctuation "
                "({punctuation}) before matching. Don't include any boundary "
                "punctuation in your keywords."
            ).format(
                punctuation=constants.GSM_WHITELIST_PUNCTUATION
            )
            errors['keyword'].append(msg)

        if errors:
            raise ValidationError(errors)


class SMSResponseTemplate(TimestampedBase):
    valid_placeholders = (
        'call_centre',
        'shortcode',
        'till_number',
        'year_price',
        'month_price',
    )

    class Actions(models.TextChoices):
        NONE = 'none', _('No Action')
        TASK = 'task', _('Create Task')
        JOIN = 'join', _('Join Customer')
        STOP = 'stop', _('Stop Customer')

    name = models.CharField(_('name'), max_length=255, unique=True)
    keywords = models.ManyToManyField('SMSResponseKeyword', related_name='responses')
    sender = models.CharField(
        _('sender'),
        max_length=20,
        blank=False,
        null=False,
        help_text=_("The sender ID this response will be sent from.")
    )
    action = models.CharField(
        _('action'),
        max_length=20,
        choices=Actions.choices,
        default=Actions.NONE,
        help_text=_("The action to take when this messages is received. E.g. create a task, "
                    "or join or stop the customer. If no action is specified, the text "
                    "in this template will be automatically sent with no staff involvement.")
    )
    assign_category = models.ForeignKey(
        'customers.CustomerCategory',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_("Customers will have the chosen category added. Leave "
                    "blank to skip category assignment.")
    )
    all_countries = models.BooleanField(
        _('all countries'),
        default=True,
        help_text=_("This template is used for incoming SMS messages from any country.",),
    )
    countries = models.ManyToManyField(
        'world.Border',
        blank=True,
        limit_choices_to={'level': 0},
        help_text=_("The countries that this template responds to.", ),
    )
    protected = models.BooleanField(
        default=False,
        help_text=_("Specifies whether template is protected from deletion and name changes.")
    )

    class Meta:
        verbose_name = "SMS response template"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        old = SMSResponseTemplate.objects.filter(pk=self.pk).first()
        if old and old.protected and old.name != self.name:
            raise ValidationError("Protected template's name must not be changed")
        super().save(*args, **kwargs)


class SMSResponseTranslation(TimestampedBase):
    language = models.CharField(
        _("language"),
        max_length=3,  # ISO 639-3 code
        choices=LANGUAGES.choices,
        default=LANGUAGES.ENGLISH,
    )
    text = models.TextField(
        _("text"),
        help_text=_(
            "Valid placeholder values are: {all_valid}. Write as " "{{{example}}}"
        ).format(
            all_valid=", ".join(SMSResponseTemplate.valid_placeholders),
            example=SMSResponseTemplate.valid_placeholders[0],
        ),
    )
    template = models.ForeignKey(
        'sms.SMSResponseTemplate',
        blank=False,
        null=False,
        on_delete=models.CASCADE,
        related_name='translations',
    )

    def validate_unique(self, exclude=None):
        """
        Validate the uniqueness at the db level. This should never fail.
        """
        super().validate_unique(exclude)
        # Ensure self is the only response in this template with this language
        count = SMSResponseTranslation.objects.filter(
            template=self.template, language=self.language
        ).count()
        if count > 1:
            # Raise a sentry_sdk issue rather than a ValidationError, because
            # the later could make the user get stuck without the ability to fix it.
            sentry_sdk.capture_message(f"SMSResponseTranslation({self.pk}: Only one response for "
                                       f"each language is allowed but {count} found")
            # raise ValidationError(
            #     message="Only one response for each language is allowed.",
            #     code="unique_together",
            # )

    def clean_fields(self, exclude=None):
        errors = defaultdict(list)

        try:
            formatted = utils.populate_templated_text(self.text)
        except KeyError as e:
            for key in e.args:
                errors['text'].append(
                    _("Placeholder '{{{key}}}' is not recognised.").format(
                        key=key)
                )
            errors['text'].append(
                _("Valid placeholder values are: {}").format(
                    ", ".join(SMSResponseTemplate.valid_placeholders)
                )
            )
        else:
            pages = SMSGateway().split_text_into_pages(formatted)
            if len(pages) > MAX_SMS_PER_MESSAGE:
                _new_line = '\n'
                message = _(
                    f'This template formats to: {len(pages)} separate SMS messages, '
                    f'above the limit of {MAX_SMS_PER_MESSAGE}: {_new_line.join(pages)}'
                )
                errors['text'].append(message)
            else:
                try:
                    formatted = utils.clean_sms_text(formatted, strip=False)  # The return value is unused
                except ValueError as e:
                    for message in e:
                        errors['text'].append(message)

        try:
            super().clean_fields(exclude)
        except ValidationError as e:
            errors.update(e.message_dict)

        if errors:
            raise ValidationError(errors)


@receiver(pre_delete, sender=SMSResponseTemplate)
def protect_from_deletion(sender, instance, using, *args, **kwargs):
    if instance.protected:
        raise ValidationError('Protected templates can not be deleted')

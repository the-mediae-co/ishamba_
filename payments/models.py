import random
import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.safestring import mark_safe
from django.utils.timezone import localtime, now
from django.utils.translation import gettext_lazy as _

from core.fields import SMSCharField
from core.models import TimestampedBase

from . import constants


class Offer(TimestampedBase):
    """ A base model for all offers. """

    FREE_SUBSCRIPTION = 1
    VERIFY_IN_STORE = 2

    _specific_subclass = models.CharField(max_length=200)
    name = models.CharField(_('name'), max_length=100, unique=True)
    expiry_date = models.DateField(
        _('expiry date'),
        help_text=_("The offer will be valid up to the end of this date in the local timezone."))

    class Meta:
        ordering = "-expiry_date",

    @property
    def specific(self):
        return getattr(self, self._specific_subclass)

    def save(self, *args, **kwargs):
        class_name = self.__class__.__name__.lower()
        if class_name == "offer":
            return self.specific.save(*args, **kwargs)
        self._specific_subclass = class_name
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def is_current(self, date=None):
        date = date or localtime(now()).date()
        return self.expiry_date >= date

    @property
    def take_up(self):
        # LBYL, rather than EAFP, but it can't hurt
        voucher_count = self.vouchers.count()
        if voucher_count:
            take_up = 100 * Decimal(self.vouchers.exclude(used_by=None).count()) / Decimal(self.vouchers.count())
        else:
            take_up = Decimal('0')
        return mark_safe("{}&nbsp;%".format(take_up.quantize(Decimal('.1'))))

    @property
    def redeemed_vouchers(self):
        return self.vouchers.exclude(used_by=None).count()

    def generate_codes(self, count):
        try:
            # start = self.vouchers.order_by('number').last().number + 1
            start = self.vouchers.latest('number').number + 1
        except Voucher.DoesNotExist:
            start = 0
        generated = []
        for n in range(start, start + count):
            generated.append(Voucher.objects.create(offer=self, number=n))
        return generated


class FreeSubscriptionOffer(Offer):
    offer_type = Offer.FREE_SUBSCRIPTION

    months = models.PositiveSmallIntegerField(
        _('months'), blank=True, null=True,
        help_text=_("How many months does this give the customer?"))


class VerifyInStoreOffer(Offer):
    offer_type = Offer.VERIFY_IN_STORE

    message = SMSCharField(
        ('message'),
        help_text=_("Must contain a string of X's to represent the code, "
                    "length to match the specified code length."))
    confirmation_message = SMSCharField(
        ('confirmation message'), blank=True,
        help_text=_("Response to send to a retailer when a verify-in-store "
                    "voucher is valid."))

    def clean_fields(self, *args, **kwargs):
        super().clean_fields(*args, **kwargs)
        pattern = constants.CODE_REGEX_TEMPLATE.format(code_length=constants.CODE_LENGTH)
        result = re.match(pattern, self.message)
        if not result:
            xs = 'X' * constants.CODE_LENGTH
            raise ValidationError({
                'message': 'Message must contain "{}" exactly once, to '
                           'represent the code.'.format(xs)})


def generate_nonce(code_length=constants.CODE_LENGTH):
    """
    (Presumably) on init, generate a random nonce value to obstruct systematic
    guessing of valid voucher codes.
    """
    # valid characters are uppercase letters and numbers, excluding I, O, 0, 1
    valid_characters = 'ABCDEFGH' + 'JKLMN' + 'PQRSTUVWXYZ' + '23456789'
    nonce = "".join(random.choice(valid_characters) for x in range(code_length))
    try:
        Voucher.objects.get(code=nonce)
    except Voucher.DoesNotExist:
        return nonce
    else:
        return generate_nonce(code_length)


class Voucher(TimestampedBase):

    offer = models.ForeignKey('Offer', related_name='vouchers', on_delete=models.CASCADE)
    number = models.PositiveSmallIntegerField(_('number'))
    code = models.CharField(_('code'), max_length=100, default=generate_nonce)
    used_by = models.ForeignKey('customers.Customer', blank=True, null=True,
                                related_name="used_vouchers", on_delete=models.SET_NULL)

    class Meta:
        ordering = ('offer', 'number')
        unique_together = (
            ('offer', 'number'),
            ('offer', 'code'),
        )

    def __str__(self):
        return self.code

    def format_message(self):
        """ Replace a string of X's in the template with self.code. """
        message = self.offer.message.replace('X' * constants.CODE_LENGTH,
                                             self.code)
        if not re.match(self.code, message):
            raise ValueError("Message template code insertion failed")

    def is_valid(self, date=None):
        date = date or localtime(now()).date()
        return self.offer.is_current(date) and self.used_by is None

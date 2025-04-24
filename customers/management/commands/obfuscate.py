from itertools import zip_longest
from random import randint
from typing import Iterable, Optional, Tuple

import phonenumbers
from django.core.management import BaseCommand
from django.db import connection
from django.db.utils import IntegrityError
from faker import Faker
from retrying import retry  # https://github.com/rholder/retrying
from django_tenants.management.commands import InteractiveTenantOption

from customers.models import Customer


def generate_phone_number(prefix, length, max_iter=1000):
    """Generate random phone number for a given country code (prefix) and length,
    with digifarm +492 prefix handling special-cased.
    Gives up after max_iter iterations.
    """
    if prefix == 49:
        prefix = 492
        length -= 1
    lower = int('9' * (length - 1))
    upper = int('9' * length)
    tries = 0
    while (tries := tries + 1) < max_iter:
        phone_number = '{}{}{}'.format('+', prefix, randint(int(lower), int(upper)))
        if phonenumbers.is_valid_number(phonenumbers.parse(phone_number)):
            return phone_number
    print(f'Failed to generate random number for prefix {prefix}, length {length}')
    return None


def grouper(iterable, n, fillvalue=None):
    """Collect data into fixed-length chunks or blocks"""
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


def retry_if_unique_error(exception):
    """Return True if we should retry (in this case when it's an IntegrityError), False otherwise"""
    if isinstance(exception, IntegrityError):
        print("DB UNIQUE ERROR: Retrying")
    return isinstance(exception, IntegrityError)


def obfuscate_customer(faker: Faker, customer: Customer) -> Optional[Customer]:
    """Obfuscates customer name and phone and returns modified customer.
    If customer can not be obfuscated returns None.
    """
    if customer is None or customer.phone is None:
        return None
    pre_nat_num = str(customer.phone.national_number)
    pre_length = len(pre_nat_num)
    if new_phone := generate_phone_number(customer.phone.country_code, pre_length):
        customer.phone = new_phone
        customer.africas_talking_phone = new_phone
        customer.name = faker.name()
        return customer
    return None


@retry(retry_on_exception=retry_if_unique_error, stop_max_attempt_number=20)
def obfuscate_customer_group(faker: Faker, group: Iterable[Customer]) -> Tuple[int, int]:
    to_update = []
    skipped = 0
    for customer in group:
        if customer is None:
            continue  # grouper pads last group with None on the right
        if obfuscated := obfuscate_customer(faker, customer):
            to_update.append(obfuscated)
        else:
            print(f'Skipping obfuscation for customer {customer}')
            skipped += 1
    Customer.objects.bulk_update(to_update, fields=['name', 'phone'])
    return len(to_update), skipped


class Command(BaseCommand, InteractiveTenantOption):
    help = 'Obfuscate all customer records in the database, within a given tenant schema'

    def add_arguments(self, parser):
        # Hack alert: we are on purpose not calling super().add_arguments(parser), because InteractiveTenantOption
        # automatically adds unneeded argument "command". Instead, we add -s/--schema which we know is processed
        # by InteractiveTenantOption.
        parser.add_argument('--batch-size', default=500, type=int, help='Number records obfuscated at once')
        parser.add_argument(
            "-s", "--schema", dest="schema_name", help="specify tenant schema"
        )

    def handle(self, batch_size: int, *args, **options):
        raise Exception(f"UPDATE_ME to support multiple phones before using")
        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)

        # Instantiate the fake name generator
        faker = Faker()

        # Create QuerySet of all Customers
        customer_set = Customer.objects.all()
        total_customer_records = customer_set.count()
        print("Total records:", total_customer_records)

        chunk_count, obfuscated_count, skipped_count = 0, 0, 0

        for chunk in grouper(customer_set, batch_size):
            chunk_count += 1
            obfuscated, skipped = obfuscate_customer_group(faker, chunk)
            obfuscated_count += obfuscated
            skipped_count += skipped
            print("Obfuscated:", chunk_count * batch_size, "of", total_customer_records)

        print(f'Obfuscated total of {obfuscated_count} customers, skipped {skipped_count}.')

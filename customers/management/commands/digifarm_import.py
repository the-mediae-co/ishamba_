
import argparse
import csv

from django.utils import timezone
from django.core.management.base import BaseCommand

from customers.models import Customer
from calls.tests.util import generate_phone_number


class Command(BaseCommand):
    help = 'Import digifarm farmer ids for existing customers'

    def add_arguments(self, parser):
        parser.add_argument('input_file', nargs='?', type=argparse.FileType('r'))

    def handle(self, input_file=None, *args, **options):
        raise Exception(f"UPDATE_ME to support multiple phones before using")
        reader = csv.reader(input_file)
        id_to_number = {fid: num for num, fid in reader}
        number_to_id = {num: fid for fid, num in id_to_number.items()}
        make_inactive = []

        self.stdout.write("Found {} records to migrate".format(len(id_to_number)))

        # Find customers with matching digifarm ids
        already_on_digifarm = Customer.objects.filter(digifarm_farmer_id__in=id_to_number.keys())
        self.stdout.write("Found {} customers already on digifarm".format(already_on_digifarm.count()))

        for customer in already_on_digifarm.iterator():
            # Update those customers to record the real phone number
            customer.africas_talking_phone = id_to_number[customer.digifarm_farmer_id]
            customer.save(update_fields=['africas_talking_phone'])
            make_inactive.append(customer.africas_talking_phone)
            self.stdout.write("Retiring {}".format(customer.africas_talking_phone))

        # Make their original accounts inactive
        Customer.objects.filter(phones__number__in=make_inactive).update(has_requested_stop=True,
                                                                stop_method=STOP_METHODS.DIGIFARM,
                                                                stop_date=timezone.now().date()
                                                                )

        # Find active customers based on provided phone numbers
        original_customers = Customer.objects.should_receive_messages().filter(phones__number__in=number_to_id.keys())
        self.stdout.write("Found {} customers to migrate".format(original_customers.count()))

        for customer in original_customers.iterator():
            # Update those customers to record the digifarm id, their original phonenumber and make a fake one for digifarm
            customer.africas_talking_phone = customer.phone
            customer.digifarm_farmer_id = number_to_id[str(customer.phone)]
            customer.phone = generate_phone_number()
            customer.save(update_fields=['africas_talking_phone', 'digifarm_farmer_id', 'phone'])
            self.stdout.write("Updating {}".format(customer.africas_talking_phone))

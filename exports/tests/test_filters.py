from unittest import skip

from django.contrib.gis.geos import GEOSGeometry

from core.constants import SEX
from core.test.cases import TestCase

from customers.models import Customer
from world.models import Border

from ..filters import CustomerExportFilter

CUSTOMER_ATTRS = {
    'name': 'John Smith',
    'sex': SEX.MALE,
    'county': 'County',
    'village': 'Village',
    'ward': 'Ward',
}


class ExportsTestCase(TestCase):

    # def setUp(self):
        # CUSTOMER_ATTRS['county'] = Border.objects.get(country='Kenya', name='county', name_en='county',
        #                                               border=GEOSGeometry('POLYGON(( 10 10, 10 20, 20 20, 20 15, 10 10))'))


    @skip("Exports is deprecated")
    def test_incomplete_records_filter(self):
        complete_fields = ['name', 'county']
        for index, field in enumerate(complete_fields):
            incomplete_data = CUSTOMER_ATTRS.copy()
            incomplete_data.pop(field)
            customer = Customer(**incomplete_data)
            customer.phone = '+25472211111{}'.format(index)
            customer.save()

        complete_customer = Customer(**CUSTOMER_ATTRS)
        complete_customer.phone = '+254722123098'
        complete_customer.save()

        queryset = Customer.objects.all()

        complete_filter = CustomerExportFilter({'incomplete_records': False}, queryset=queryset)
        incomplete_filter = CustomerExportFilter({'incomplete_records': True}, queryset=queryset)

        self.assertEqual(complete_filter.qs.count(), 2)
        self.assertEqual(incomplete_filter.qs.count(), len(complete_fields) + 1)

    @skip("Exports is deprecated")
    def test_filterset_form_contains_complete_records_filter(self):
        filter_data = {
            'name__gt': '',
        }
        complete_filter = CustomerExportFilter({'incomplete_records': False},
                                               queryset=Customer.objects.all())

        complete_filter.form.is_valid()
        for key, val in filter_data.items():
            self.assertEqual(complete_filter.form.cleaned_data[key], val)

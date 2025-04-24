import django_tables2 as tables
from django_tables2.utils import A

from .models import Offer


class OfferTable(tables.Table):
    name = tables.LinkColumn('offer_detail', args=[A('pk')])
    take_up = tables.Column(orderable=False, verbose_name='take-up')
    num_vouchers = tables.Column(empty_values=(), orderable=False)

    class Meta:
        model = Offer
        fields = ('name', 'expiry_date', 'num_vouchers', 'take_up')
        attrs = {"class": "table-bordered"}
        empty_text = 'No offers'
        template_name = "tables/tables.html"

    def render_num_vouchers(self, value, record, bound_column):
        return record.vouchers.count()

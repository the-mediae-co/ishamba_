from typing import Iterable

from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse, reverse_lazy
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.utils.timezone import localtime, now
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DetailView, FormView, UpdateView
from django.views.generic.edit import FormMixin

from django_tables2 import SingleTableView

from core.importer.resources import VoucherResource
from customers.models import Customer
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS
from sms.tasks import send_message
from sms.views import BaseFilterFormView

from . import constants
from .forms import (FreeSubscriptionOfferForm, GenerateVouchersForm,
                    OfferVerifyForm, VerifyInStoreOfferForm)
from .models import FreeSubscriptionOffer, Offer, VerifyInStoreOffer, Voucher
from .tables import OfferTable


class OfferListView(SingleTableView):

    model = Offer
    template_name = 'offers/offer_list.html'
    table_class = OfferTable


class OfferDetailView(FormMixin, DetailView):

    model = Offer
    template_name = 'offers/offer_detail.html'
    form_class = GenerateVouchersForm

    def get(self, request, *args, **kwargs):
        """ Rewrite to include serving the download, if the export kwarg is present.
        """
        self.object = self.get_object()
        if request.GET.get('export', False):
            return self.export_vouchers()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_success_url(self):
        return reverse('offer_detail', args=(self.object.pk,))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # add a GenerateVouchersForm instance for FreeSubscriptionOffer
        # instances only
        if isinstance(self.object.specific, FreeSubscriptionOffer):
            context['form'] = self.get_form(self.get_form_class())
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form(self.get_form_class())
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        count = form.cleaned_data['number_to_generate']
        self.object.specific.generate_codes(count)
        return super().form_valid(form)

    def export_vouchers(self):
        queryset = self.object.vouchers.all()
        voucher_resource = VoucherResource().export(queryset)

        response = HttpResponse(voucher_resource.csv, content_type='text/csv')
        filename = "{slug}_{date}.csv".format(slug=slugify(self.object.name),
                                              date=localtime(now()).isoformat())
        response['Content-Disposition'] = 'attachment; filename={}'.format(filename)
        response['Content-Length'] = len(response.content)
        return response


class OfferVerifyView(FormView):
    """ Allows CCOs to manually verify an offer and consume the voucher code
    if it is valid.
    """
    form_class = OfferVerifyForm
    template_name = 'offers/offer_verify.html'
    success_url = reverse_lazy('offer_verify')

    def form_valid(self, form):
        code = form.cleaned_data.get('code')
        phone = form.cleaned_data.get('phone')
        customer = Customer.objects.get(phones__number=phone)
        voucher = Voucher.objects.get(code=code)
        voucher.used_by = customer
        voucher.save(update_fields=['used_by'])

        messages.success(
            self.request,
            _("The voucher %(code)s is valid.") % {'code': code})

        return super().form_valid(form)


class FreeSubscriptionOfferCreateView(SuccessMessageMixin, CreateView):

    model = FreeSubscriptionOffer
    form_class = FreeSubscriptionOfferForm
    template_name = 'offers/offer_form.html'
    success_message = "%(name)s was created successfully"

    def get_context_data(self, *args, **kwargs):
        kwargs['url_name'] = 'free_subscription_offer_create'
        return super().get_context_data(*args, **kwargs)

    def get_success_url(self):
        return reverse('offer_detail', args=(self.object.pk,))


class VerifyInStoreOfferCreateView(SuccessMessageMixin, CreateView):

    model = VerifyInStoreOffer
    form_class = VerifyInStoreOfferForm
    template_name = 'offers/offer_form.html'
    success_message = "%(name)s was created successfully"

    def get_context_data(self, *args, **kwargs):
        kwargs['url_name'] = 'verify_in_store_offer_create'
        return super().get_context_data(*args, **kwargs)

    def get_success_url(self):
        return reverse('offer_detail', args=(self.object.pk,))


class OfferUpdateView(SuccessMessageMixin, UpdateView):

    model = Offer
    template_name = 'offers/offer_form.html'
    success_message = "%(name)s was updated successfully"

    def get_success_url(self):
        return reverse('offer_detail', args=(self.object.pk,))

    def get_form_class(self):
        if isinstance(self.object.specific, FreeSubscriptionOffer):
            return FreeSubscriptionOfferForm
        if isinstance(self.object.specific, VerifyInStoreOffer):
            return VerifyInStoreOfferForm


class OfferFilterCustomersView(BaseFilterFormView):

    template_name = 'offers/offer_filter_form.html'
    form_action = 'offer_filter_customers'
    form_button_text = 'Send now'

    def get_success_url(self):
        return reverse('offer_detail', args=(self.offer.pk,))

    def form_valid_next(self, form, customers: Iterable[Customer], count):
        vouchers = self.offer.generate_codes(count)
        for customer, voucher in zip(customers, vouchers):
            text = self.offer.specific.message.replace('X' * constants.CODE_LENGTH, voucher.code)
            if voucher:
                extra = {'voucher_id': voucher.id}
            else:
                extra = {}
            voucher_sms = OutgoingSMS.objects.create(text=text,
                                                     extra=extra,
                                                     message_type=OUTGOING_SMS_TYPE.VOUCHER)
            send_message.delay(voucher_sms.id, [customer.id], sender=settings.SMS_SENDER_SUBSCRIPTION)
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['offer'] = self.offer
        return context

    def post(self, request, *args, **kwargs):
        """ Mimic SingleObjectMixin, by assigning self.offer.
        """
        self.offer = get_object_or_404(Offer, pk=self.kwargs['pk'])
        return super().post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        """ Mimic SingleObjectMixin, by assigning self.offer.
        """
        self.offer = get_object_or_404(Offer, pk=self.kwargs['pk'])
        return super().get(request, *args, **kwargs)

    def filter_customers(self, customers, form):
        """ Does nothing for now. We could in future choose to exclude
        customers who've previously received this offer.
        """
        return super().filter_customers(customers, form)

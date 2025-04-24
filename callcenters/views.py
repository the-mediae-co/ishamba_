from django.shortcuts import redirect, render
from django.views.generic import FormView

from callcenters.forms import ChooseCallCenterForm
from callcenters.models import CallCenterOperator


class CallCentresIndexFormView(FormView):
    """
    The index of the call center. This is a FormView because on GET abs
    choose phone page will be selected (to allow the operator to choose the
    phone he's using). On POST (and form_valid) the normal index will be
    displayed after creating the operator's PusherSession.

    Warning: This form won't redirect on POST - however this seems to be the
    best way to implement this.
    """
    template_name = 'callcenters/form.html'
    form_class = ChooseCallCenterForm

    def form_valid(self, form):
        call_center = form.cleaned_data['call_center']
        user = self.request.user

        CallCenterOperator.objects.filter(
            call_center=call_center, operator=user, active=True
        ).update(current=True)
        CallCenterOperator.objects.filter(
            operator=user, active=True, current=True
        ).exclude(call_center=call_center).update(current=False)

        return redirect('call_centers_index')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

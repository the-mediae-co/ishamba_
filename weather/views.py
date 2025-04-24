from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import FormView

from . import forms


class CountyForecastUploadView(FormView):

    form_class = forms.CountyForecastUploadForm
    success_url = reverse_lazy('admin:weather_countyforecast_changelist')
    template_name = "admin/weather/countyforecast/upload.html"

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        form.save(user=self.request.user)
        return super().form_valid(form)

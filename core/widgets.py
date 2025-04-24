from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms.widgets import TextInput

from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget
from django_select2.views import AutoResponseView


class HTML5DateInput(TextInput):
    input_type = 'date'


class HTML5DateTimeInput(TextInput):
    input_type = 'datetime-local'


class AuthSelect2View(LoginRequiredMixin, AutoResponseView):
    pass


class AuthSelect2WidgetMixin(object):
    def __init__(self, *args, **kwargs):
        kwargs['data_view'] = 'auth_select2_view'
        super(AuthSelect2WidgetMixin, self).__init__(*args, **kwargs)


class AuthModelSelect2Widget(AuthSelect2WidgetMixin, ModelSelect2Widget):
    pass


class AuthModelSelect2MultipleWidget(AuthSelect2WidgetMixin, ModelSelect2MultipleWidget):
    pass

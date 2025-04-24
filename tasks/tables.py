import django_tables2 as tables
from django.utils import formats, translation
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from markdown import markdown

from .models import Task, TaskUpdate


class TaskTable(tables.Table):
    bulk = tables.TemplateColumn(template_name='tasks/partials/bulk_column.html',
                                 verbose_name='',
                                 orderable=False)
    created = tables.TemplateColumn(template_name='tasks/partials/created_column.html',
                                    verbose_name=_('Created'))
    last_updated = tables.TemplateColumn(template_name='tasks/partials/created_column.html',
                                         verbose_name=_('Last updated'))
    status = tables.TemplateColumn(verbose_name=_('Status'), template_name='tasks/partials/status_column.html')
    priority = tables.TemplateColumn(template_name='tasks/partials/priority_column.html')
    tags = tables.TemplateColumn(template_name='tasks/partials/tags_column.html')
    assignees = tables.TemplateColumn(template_name='tasks/partials/assignees_column.html')
    responses = tables.TemplateColumn(template_name='tasks/partials/responses_column.html',
                                      verbose_name=_('Responses'))
    customer_id = tables.TemplateColumn(template_name='tasks/partials/customer_id_column.html',
                                        verbose_name=_('Customer ID'))
    customer_border0 = tables.TemplateColumn(template_name='tasks/partials/customer_country_column.html',
                                            verbose_name=_('Country'))
    customer_border1 = tables.TemplateColumn(template_name='tasks/partials/customer_county_column.html',
                                            verbose_name=_('County/region'))
    customer_has_gps = tables.TemplateColumn(template_name='tasks/partials/customer_has_gps_column.html',
                                             verbose_name=_('Has GPS'))
    edit = tables.TemplateColumn(template_name='tasks/partials/id_column.html',
                                 verbose_name='Edit',
                                 orderable=False)

    formatted_phone = tables.Column(accessor="customer__formatted_phone", verbose_name=_("Phone Number"), visible=False)

    class Meta:
        model = Task
        fields = ('bulk', 'created', 'last_updated', 'description', 'responses', 'status', 'formatted_phone',
                  'priority', 'tags', 'assignees', 'customer_id', 'customer_border0', 'customer_border1',
                  'customer_has_gps', 'edit')
        attrs = {"class": "table-bordered"}
        empty_text = 'No tasks'
        template_name = 'tables/tables.html'
        # No order_by is declared here because we set the default
        # queryset order in TaskTableView.get_queryset()

    # Value extraction methods for use in exporting to csv/xls
    # https://django-tables2.readthedocs.io/en/stable/pages/custom-data.html#table-value-foo-methods

    def value_created(self, record):
        if record:
            # Return absolute date instead of elapsed time
            format_string = formats.get_format("DATETIME_INPUT_FORMATS", lang=translation.get_language())[0]
            return record.created.strftime(format_string)

    def value_last_updated(self, record):
        if record:
            # Return absolute date instead of elapsed time
            format_string = formats.get_format("DATETIME_INPUT_FORMATS", lang=translation.get_language())[0]
            return record.last_updated.strftime(format_string)

    def value_responses(self, record):
        return "\n".join(sms.text for sms in record.outgoing_messages.all())

    def value_status(self, value):
        return value

    def value_priority(self, value):
        return value

    def value_tags(self, value):
        if value:
            return ",".join(value.values_list('name', flat=True))

    def value_assignees(self, value):
        if value:
            return ",".join(value.values_list('username', flat=True))

    def value_customer_id(self, record):
        if record:
            return record.customer.pk

    def value_customer_has_gps(self, record):
        if record and record.customer and record.customer.location:
            location = record.customer.location
            # Ensure location has x and y attributes
            x = getattr(location, 'x', None)
            y = getattr(location, 'y', None)

            # Check if both coordinates are available
            if x is not None and y is not None:
                return f"{y}, {x}"  # Return coordinates in 'latitude, longitude' format
        return ''  # Return empty string if location or coordinates are missing

    # https://django-tables2.readthedocs.io/en/stable/pages/custom-data.html#table-render-foo-methods
    def render_customer_has_gps(self, record):
        if record and record.customer and record.customer.location:
            return '✅'  # Display checkmark if location is available
        return ''  # Return empty string if location is not available
    def value_customer_border0(self, record):
        if record:
            return record.customer.border0

    def value_customer_border1(self, record):
        if record:
            return record.customer.border1

    # https://django-tables2.readthedocs.io/en/latest/pages/ordering.html
    def order_priority(self, queryset, is_descending):
        """ Sort via the priority column: critical > high > medium > low priority """
        queryset = Task.order_by_priority(queryset, is_descending)
        return queryset, True


class TaskUpdateTable(tables.Table):
    creator = tables.Column(orderable=False)

    class Meta:
        model = TaskUpdate
        fields = ('created', 'creator', 'message', 'status', )
        order_by = ('created', )
        attrs = {"class": "table-bordered"}
        empty_text = 'No updates for this task'
        template_name = 'tables/tables.html'

    def render_message(self, value):
        return mark_safe(markdown(value))

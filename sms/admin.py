from django.contrib import admin
from django.core.exceptions import ValidationError
from django import forms
from djangoql.admin import DjangoQLSearchMixin
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from core.admin import TimestampedBaseAdmin

from gateways import Gateway
from .models import (OutgoingSMS, IncomingSMS, SMSResponseKeyword,
                     SMSResponseTemplate, SMSResponseTranslation)


@admin.register(IncomingSMS)
class IncomingSMSAdmin(TimestampedBaseAdmin):
    list_display = ('at', 'sender', 'customer', 'text')
    search_fields = (
        'text', 'sender', 'customer__name',
        'customer__border0__name', 'customer__border1__name', 'customer__border2__name', 'customer__border3__name'
    )
    list_display_links = None
    # list_filter = ('at', )


@admin.register(OutgoingSMS)
class OutgoingSMSAdmin(DjangoQLSearchMixin, TimestampedBaseAdmin):
    list_display = ('text', 'time_sent', 'recipients', 'at_recipients', 'df_recipients')
    search_fields = ('text', 'time_sent')
    list_filter = ('time_sent', )

    def recipients(self, obj):
        return obj.get_extant_recipients().count()

    def at_recipients(self, obj):
        return obj.get_extant_recipients().filter(recipient__digifarm_farmer_id__isnull=True).count()

    def df_recipients(self, obj):
        return obj.get_extant_recipients().filter(recipient__digifarm_farmer_id__isnull=False).count()


@admin.register(SMSResponseKeyword)
class SMSResponseKeywordAdmin(TimestampedBaseAdmin):
    model = SMSResponseKeyword
    list_display = ('keyword', 'is_active', 'response_templates',)
    search_fields = ('keyword',)
    # Note that TimestampedBaseAdmin adds exclude and readonly_fields
    readonly_fields = ('response_templates',)

    @admin.display(description='Response Templates')
    def response_templates(self, instance):
        if instance.responses.count() > 0:
            output = format_html_join(
                mark_safe(', '),
                '<a href={}>{}</a>',
                ((f"/admin/sms/smsresponsetemplate/{pk}/change/", name,)
                 for pk, name in instance.responses.values_list('pk', 'name')),
            )
            return output
        return mark_safe('')

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            # In general, admins are allowed to delete keywords
            return True
        # Only permit keywords to be deleted if they are no longer used in response templates
        return obj.responses.count() == 0


class SMSResponseKeywordInlineForm(forms.BaseInlineFormSet):
    """
    Change the queryset for SMSResponseKeyword choice menu to exclude the
    blank ('') keyword, and to sort them via keyword
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.forms:
            form.fields['smsresponsekeyword'].queryset = SMSResponseKeyword.objects.exclude(keyword='').order_by('keyword')


class SMSResponseKeywordInline(admin.TabularInline):
    model = SMSResponseKeyword.responses.through
    extra = 1
    can_delete = True
    formset = SMSResponseKeywordInlineForm


class SMSResponseTranslationInlineForm(forms.BaseInlineFormSet):
    """
    Protect against multiple entries for the same language.
    Protect against zero responses.
    """
    def clean(self):
        super().clean()
        num_forms = self.data.get('translations-TOTAL_FORMS')
        if not num_forms or int(num_forms) < 1:
            raise ValidationError(f"At least one translation is required.")
        num_forms = int(num_forms)
        languages = {}
        for n in range(num_forms):
            lang = self.data.get(f'translations-{n}-language')
            delete = self.data.get(f'translations-{n}-DELETE')
            if delete and delete == 'on':
                num_forms -= 1
            else:
                if lang and lang in languages:
                    raise ValidationError(f"Only one translation for each language is allowed.")
            languages[lang] = True
        if num_forms < 1:
            raise ValidationError(f"At least one translation is required.")
        return self.data


class SMSResponseTranslationInline(admin.TabularInline):
    model = SMSResponseTranslation
    extra = 0
    can_delete = True
    formset = SMSResponseTranslationInlineForm
    exclude = ('creator_id', 'created', 'last_editor_id', 'last_updated')
    verbose_name = 'translation'
    verbose_name_plural = 'translations'


class SMSResponseTemplateAdminForm(forms.ModelForm):
    sender = forms.ChoiceField(choices=Gateway.get_sender_choices,
                               label=_("Sender"),
                               help_text=_("Sender: The sender ID this response will be sent from."),
                               required=True)

    class Meta:
        model = SMSResponseTemplate
        fields = ('name', 'sender', 'action', 'assign_category', 'all_countries', 'countries',)

    def clean(self):
        data = super().clean()
        my_all_countries = data.get('all_countries')
        my_countries = data.get('countries')
        # Ensure that either there is a selection of countries, or the all_countries flag is set
        if not my_all_countries and my_countries.count() == 0:
            raise ValidationError(
                _(f"This template must either apply to all countries, "
                  f"or at least one selected country."),
                params={},
            )

        if not my_all_countries:
            country_names = my_countries.values_list('name', flat=True)
            choices = Gateway.get_sender_choices(country_names)
        else:
            choices = Gateway.get_sender_choices()

        machine_choices = [str(c[0]) for c in choices]
        if data.get('sender') not in machine_choices:
            # Convert from choices tuple to a human-readable list
            human_choices = [c[1] for c in choices]
            message = _(f'Invalid sender. Must be one of {human_choices}')
            self.add_error('sender', message)

        num_keywords = int(self.data.get('SMSResponseTemplate_keywords-TOTAL_FORMS', 0))
        for index in range(num_keywords):
            key = f"SMSResponseTemplate_keywords-{index}-smsresponsekeyword"
            raw_key_value = self.data.get(key)
            if isinstance(raw_key_value, str):
                if not raw_key_value.isnumeric():
                    # Empty fields are represented by an empty string '', which cannot be converted to ints, so ignore.
                    continue
            kw_pk = int(raw_key_value)
            if kw_pk:
                try:
                    kw = SMSResponseKeyword.objects.get(pk=kw_pk)
                    responses = kw.responses.all()
                    if self.instance.pk:
                        # If we're editing a response template already in the db, exclude it from the dup check
                        my_response = SMSResponseTemplate.objects.filter(pk=self.instance.pk)
                        responses = responses.difference(my_response)
                    for r in responses:
                        other_countries = r.countries.difference(my_countries)
                        intersecting_countries = my_countries.intersection(other_countries)
                        if r.all_countries or (my_all_countries and other_countries.count() > 0) or intersecting_countries:
                            raise ValidationError(
                                _(f"Keyword {kw.keyword} used in another SMSResponseTemplate ({r}) for the same country")
                            )
                except (SMSResponseKeyword.DoesNotExist, SMSResponseTemplate.DoesNotExist):
                    pass

        return data


@admin.register(SMSResponseTemplate)
class SMSResponseTemplateAdmin(TimestampedBaseAdmin):
    form = SMSResponseTemplateAdminForm
    list_display = ('name', 'is_active', 'action', 'sender', 'for_countries', 'keyword_triggers')
    search_fields = ('name', 'translations__text', 'translations__language', 'sender', 'countries__name', 'countries__name_en')
    # Note that TimestampedBaseAdmin adds exclude and readonly_fields
    fields = ('name', 'sender', 'action', 'assign_category', 'all_countries', 'countries',)

    inlines = [
        SMSResponseTranslationInline,
        SMSResponseKeywordInline,
    ]

    class Media:
        js = (
            'js/template-admin-controls.js?version=2',
        )

    def is_active(self, obj):
        return obj.keywords.filter(is_active=True).exists()

    @admin.display(description='Keywords')
    def keyword_triggers(self, instance):
        if instance.keywords.count() > 0:
            output = format_html_join(
                mark_safe(', '),
                '<a href={}>{}</a>',
                ((f"/admin/sms/smsresponsekeyword/{pk}/change/", name,)
                 for pk, name in instance.keywords.values_list('pk', 'keyword')),
            )
            return output
        return mark_safe('')

    def for_countries(self, obj):
        if obj.all_countries:
            return mark_safe('ALL')
        elif obj.countries.count() > 0:
            return ', '.join(obj.countries.values_list('name', flat=True))
        return mark_safe('-')

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        all_countries = form.cleaned_data.get('all_countries')
        # If this template applies to all countries, remove any individual country selections
        if all_countries:
            form.instance.countries.clear()

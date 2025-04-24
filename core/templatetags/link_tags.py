from django import template
from django.urls import reverse

register = template.Library()


@register.inclusion_tag('core/includes/breadcrumb_entry.html', takes_context=True)
def breadcrumb_entry(context, text, url_name, **kwargs):
    # Defensively ensure that pk is set
    if 'pk' in kwargs and kwargs.get('pk') == '':
        kwargs['pk'] = context.request.resolver_match.kwargs.get('pk')
    url = reverse(url_name, kwargs=kwargs)
    return {
        'the_url': url,
        'text': text,
        'request': context['request'],
    }


@register.inclusion_tag('core/includes/submenu_entry.html', takes_context=True)
def submenu_entry(context, text, url_name, icon, **kwargs):
    # Defensively ensure that pk is set
    if 'pk' in kwargs and kwargs.get('pk') == '':
        kwargs['pk'] = context.request.resolver_match.kwargs.get('pk')
    url = reverse(url_name, kwargs=kwargs)
    return {
        'the_url': url,
        'text': text,
        'icon': icon,
        'request': context['request'],
    }


@register.inclusion_tag('core/includes/submenu_child.html', takes_context=True)
def submenu_child(context, text, url_name, icon, **kwargs):
    # Defensively ensure that pk is set
    if 'pk' in kwargs and kwargs.get('pk') == '':
        kwargs['pk'] = context.request.resolver_match.kwargs.get('pk')
    url = reverse(url_name, kwargs=kwargs)
    return {
        'the_url': url,
        'text': text,
        'icon': icon,
        'request': context['request'],
    }


@register.inclusion_tag('core/includes/navmenu_entry.html', takes_context=True)
def navmenu_entry(context, text, url_name, **kwargs):
    app_name = kwargs.pop('app_name', '')
    active = app_name == context['app_name']
    url = reverse(url_name, kwargs=kwargs)
    return {
        'the_url': url,
        'text': text,
        'active': active,
        'request': context['request'],
    }

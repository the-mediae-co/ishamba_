from django import template
from django.utils.encoding import force_str

register = template.Library()


@register.filter(is_safe=True)
def natural_join(items):
    """
    Returns a concatenated string for a given list of strings with the items
    separated by commas, except the last two items which are separated by "and"
    """
    items = list(map(force_str, items))

    if not items:
        output = ''
    elif len(items) == 1:
        output = items[0]
    else:
        output = (" ".join((", ".join(items[0:-1]),
                            "{} {}".format('and', items[-1]))))
    return output


@register.filter()
def values_for(list_of_dicts, arg):
    return [d.get(arg, '') for d in list_of_dicts]

from itertools import zip_longest


def grouper(iterable, n=500, fillvalue=None):
    """ Group the given iterable into chunks for batch processing

    Args:
        iterable: The iterable you want to divide into groups
        n: Optional integer to set the group size
        fillvalue: Optional value to fill last group with

    Returns:
        A generator of groups limited to the size given
    """
    args = [iter(iterable)] * n
    return zip_longest(fillvalue=fillvalue, *args)


def is_jquery_ajax(request):
    # If a jquery ajax request
    return 'x-requested-with' in request.headers and request.headers.get('x-requested-with') == 'XMLHttpRequest'

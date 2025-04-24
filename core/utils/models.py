import gc
import itertools


def queryset_iterator(queryset, chunksize=1000):
    """
    Iterate through queryset by chunks of `chunksize`.
    run the garbage collector after every chunk
    """
    if hasattr(queryset, 'iterator'):
        iterable = queryset.iterator()

    iterator = iter(iterable)

    chunk = tuple(itertools.islice(iterator, chunksize))
    while chunk:
        yield chunk

        gc.collect()

        chunk = tuple(itertools.islice(iterator, chunksize))
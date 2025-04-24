import contextlib


@contextlib.contextmanager
def dummy_contextmanager():
    yield None

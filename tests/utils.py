"""Utilities for unit tests."""

import os
from functools import wraps


def mktitle(title=None):
    """Make a test-friendly title from the given (optional) text."""

    text = os.getenv("PYTEST_CURRENT_TEST")

    if title is not None:
        text += " :: " + title

    return text


def store_retvals(func):
    """Decorator storing the return values as function attribute for later cleanups"""

    @wraps(func)
    def wrapped(*args, **kwargs):
        retval = func(*args, **kwargs)
        wrapped.retvals.append(retval)
        return retval

    wrapped.retvals = []
    return wrapped

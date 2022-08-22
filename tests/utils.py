"""Utilities for unit tests."""

import os


def mktitle(title=None):
    """Make a test-friendly title from the given (optional) text."""

    text = os.getenv("PYTEST_CURRENT_TEST")

    if title is not None:
        text += " :: " + title

    return text

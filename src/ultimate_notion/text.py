"""Utilities for working text, markdown & rich text in Notion."""

from __future__ import annotations

import re
from collections.abc import Iterator

# the max text size according to the Notion API is 2000 characters.
MAX_TEXT_OBJECT_SIZE = 2000

BASE_URL_PATTERN = r'https://(www)?.notion.so/'
UUID_PATTERN = r'[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}'

UUID_RE = re.compile(rf'^(?P<id>{UUID_PATTERN})$')

PAGE_URL_SHORT_RE = re.compile(
    rf"""^
      {BASE_URL_PATTERN}
      (?P<page_id>{UUID_PATTERN})
    $""",
    flags=re.IGNORECASE | re.VERBOSE,
)

PAGE_URL_LONG_RE = re.compile(
    rf"""^
      {BASE_URL_PATTERN}
      (?P<title>.*)-
      (?P<page_id>{UUID_PATTERN})
    $""",
    flags=re.IGNORECASE | re.VERBOSE,
)

BLOCK_URL_LONG_RE = re.compile(
    rf"""^
      {BASE_URL_PATTERN}
      (?P<username>.*)/
      (?P<title>.*)-
      (?P<page_id>{UUID_PATTERN})
      \#(?P<block_id>{UUID_PATTERN})
    $""",
    flags=re.IGNORECASE | re.VERBOSE,
)


def extract_id(text: str) -> str | None:
    """Examine the given text to find a valid Notion object ID"""

    m = UUID_RE.match(text)
    if m is not None:
        return m.group('id')

    m = PAGE_URL_LONG_RE.match(text)
    if m is not None:
        return m.group('page_id')

    m = PAGE_URL_SHORT_RE.match(text)
    if m is not None:
        return m.group('page_id')

    m = BLOCK_URL_LONG_RE.match(text)
    if m is not None:
        return m.group('block_id')

    return None


def chunky(text: str, length: int = MAX_TEXT_OBJECT_SIZE) -> Iterator[str]:
    """Break the given `text` into chunks of at most `length` size."""
    return (text[idx : idx + length] for idx in range(0, len(text), length))


def python_identifier(string: str) -> str:
    """Make a valid Python identifier

    This will remove any leading characters that are not valid and change all
    invalid interior sequences to underscore.

    Attention: This may result in an empty string!
    """
    s = re.sub(r'[^0-9a-zA-Z_]+', '_', string)
    s = re.sub(r'^[^a-zA-Z]+', '', s)
    return s.rstrip('_')


def snake_case(string: str) -> str:
    """Make a Python identifier in snake_case.

    Attention: This may result in an empty string!
    """
    return python_identifier(string).lower()


def camel_case(string: str) -> str:
    """Make a Python identifier in CamelCase.

    Attention: This may result in an empty string and a CamelCase sting will be capitalized!
    """
    return ''.join([elem.capitalize() for elem in snake_case(string).split('_')])


def decapitalize(string: str) -> str:
    """Inverse of capitalize"""
    if not string:
        return string
    return string[0].lower() + string[1:]


def html_img(url: str, size: float) -> str:
    """Create a img tag in HTML"""
    return f'<img src="{url}" style="height:{size:.2f}em">'

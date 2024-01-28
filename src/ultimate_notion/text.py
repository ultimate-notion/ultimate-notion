"""Utilities for working text, markdown & rich text in Notion."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import TYPE_CHECKING, cast

import numpy as np

from ultimate_notion.utils import rank

if TYPE_CHECKING:
    from ultimate_notion.objects import RichTextBase

MAX_TEXT_OBJECT_SIZE = 2000
"""The max text size according to the Notion API is 2000 characters."""

BASE_URL_PATTERN = r'https://(www.)?notion.so/'
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


MD_STYLES = ('bold', 'italic', 'strikethrough', 'code', 'underline')
"""Markdown styles supported by Notion."""
MD_STYLE_MAP = {
    'bold': ('**', '**'),
    'italic': ('*', '*'),
    'strikethrough': ('~~', '~~'),
    'code': ('`', '`'),
    'underline': ('<u>', '</u>'),
}
"""Mapping from markdown style to markdown symbol."""


def extract_id(text: str) -> str | None:
    """Examine the given text to find a valid Notion object ID."""

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
    """Make a valid Python identifier.

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
    """Inverse of `capitalize`."""
    if not string:
        return string
    return string[0].lower() + string[1:]


def html_img(url: str, size: float) -> str:
    """Create a img tag in HTML."""
    return f'<img src="{url}" style="height:{size:.2f}em">'


def md_spans(rich_texts: list[RichTextBase]) -> np.ndarray:
    """Convert rich text to markdown spans.

    An span is a sequence of rich texts with the same markdown style expressed as a row in the returned array.
    The value k of the j-th column corresponds to the length of the current span richt_texts[j-k:j].
    """
    spans = np.zeros((len(MD_STYLES), len(rich_texts) + 1), dtype=int)
    old_ranks = np.zeros(len(MD_STYLES), dtype=int)
    for j, rich_text in enumerate(rich_texts, start=1):
        for i, md_style in enumerate(MD_STYLES):
            annotations = rich_text.obj_ref.annotations
            if getattr(annotations, md_style) is True:
                spans[i, j] = spans[i, j - 1] + 1
        # handle the case of overlapping spans, i.e. **abc ~~def** ghi~~ -> **abc ~~def~~** ~~ghi~~
        curr_ranks = rank(-spans[:, j])
        for i in np.where(curr_ranks < old_ranks)[0]:
            spans[i, j] = 1 if spans[i, j] > 0 else 0  # start a new span if an encompassing span ends
        old_ranks = curr_ranks
    return spans


def sorted_md_spans(md_spans: np.ndarray) -> Iterator[tuple[int, int, str]]:
    """Sort the spans of the given markdown spans in the right order.

    We have to iterate from the smallest spans to the largest spans and from left to right.
    """
    sorted_spans = []
    md_spans = md_spans.copy()
    for span_len in reversed(range(1, np.max(md_spans) + 1)):
        indices = tuple(idx[::-1] for idx in np.where(md_spans == span_len))
        for i, j in zip(*indices, strict=True):
            sorted_spans.append((j - span_len, j - 1, MD_STYLES[i]))
            md_spans[i, j - span_len + 1 : j + 1] = 0
    return reversed(sorted_spans)


def rich_texts_to_markdown(rich_texts: list[RichTextBase]) -> str:
    """Convert rich text to markdown."""
    from ultimate_notion.objects import Mention  # noqa: PLC0415  # ToDo: Remove when mypy doesn't need the cast below

    def has_only_ws_chars(text: str) -> bool:
        return re.match(r'^\s*$', text) is not None

    def add_md_style(texts: list[str], start: int, end: int, md_style: str):
        # we skip text blocks with only whitespace characters
        if has_only_ws_chars(texts[start]) and start != end:
            return add_md_style(texts, start + 1, end, md_style)
        elif has_only_ws_chars(texts[end]) and start != end:
            return add_md_style(texts, start, end - 1, md_style)

        left = texts[start]
        if lmatch := re.search(r'\S', left):
            texts[start] = left[: lmatch.start()] + MD_STYLE_MAP[md_style][0] + left[lmatch.start() :]

        right = texts[end]
        if rmatch := re.search(r'\S(?=\s*$)', right):
            texts[end] = right[: rmatch.end()] + MD_STYLE_MAP[md_style][1] + right[rmatch.end() :]

        if bool(lmatch) != bool(rmatch):
            rt_objs = '\n'.join(str(rt.obj_ref) for rt in rich_texts)
            msg = f'Error when inserting markdown styles into:\n{rt_objs}'
            raise ValueError(msg)

    md_rich_texts = [rich_text.obj_ref.plain_text for rich_text in rich_texts]
    for idx, rich_text in enumerate(rich_texts):
        if rich_text.is_equation:
            md_rich_texts[idx] = '$' + rich_text.obj_ref.plain_text.strip() + '$'
        elif rich_text.is_mention:
            rich_text = cast(Mention, rich_text)
            obj_ref = rich_text.obj_ref
            match rich_text.type:
                case 'user' | 'date':
                    md_rich_texts[idx] = f'[{obj_ref.plain_text}]()'  # @ is already included
                case _:
                    md_rich_texts[idx] = f'↗[{obj_ref.plain_text}]({obj_ref.href})'

    for start, end, md_style in sorted_md_spans(md_spans(rich_texts)):
        add_md_style(md_rich_texts, start, end, md_style)

    return ''.join(md_rich_texts)

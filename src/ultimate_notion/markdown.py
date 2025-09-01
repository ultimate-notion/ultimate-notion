"""Functionality for working with Markdown in Notion."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from typing import TYPE_CHECKING, TypeGuard

import mistune
import numpy as np
from mistune.directives import FencedDirective, TableOfContents
from numpy.typing import NDArray

from ultimate_notion.obj_api.core import raise_unset
from ultimate_notion.utils import rank

if TYPE_CHECKING:
    from ultimate_notion.rich_text import Math, Mention, RichTextBase


MD_STYLES = ('bold', 'italic', 'strikethrough', 'code', 'link')
"""Markdown styles supported by Notion."""
MD_STYLE_MAP = {
    'bold': '**',
    'italic': '*',
    'strikethrough': '~~',
    'code': '`',
}
"""Mapping from markdown style to markdown symbol."""


def md_spans(rich_texts: Sequence[RichTextBase]) -> NDArray[np.int_]:
    """Convert rich text to markdown spans.

    An span is a sequence of rich texts with the same markdown style expressed as a row in the returned array.
    The value k of the j-th array column corresponds to the length of the current span richt_texts[j-k:j].
    """
    spans: NDArray[np.int_] = np.zeros((len(MD_STYLES), len(rich_texts) + 1), dtype=int)
    old_ranks: NDArray[np.int_] = np.zeros(len(MD_STYLES), dtype=int)
    prev_rich_text = None

    for j, rich_text in enumerate(rich_texts, start=1):
        for i, md_style in enumerate(MD_STYLES):
            if md_style == 'link':
                if not rich_text.is_text:
                    continue
                href = rich_text.obj_ref.href
                if href is not None:
                    prev_href = prev_rich_text.obj_ref.href if prev_rich_text is not None else None
                    if href == prev_href:  # continue current link span or start new one
                        spans[i, j] = spans[i, j - 1] + 1
                    else:
                        spans[i, j] = 1
            else:
                annotations = rich_text.obj_ref.annotations
                if getattr(annotations, md_style) is True:
                    spans[i, j] = spans[i, j - 1] + 1

        # handle the case of overlapping spans, e.g. **abc ~~def** ghi~~ -> **abc ~~def~~** ~~ghi~~
        curr_ranks = rank(-spans[:, j])
        for i in np.where(curr_ranks < old_ranks)[0]:
            spans[i, j] = 1 if spans[i, j] > 0 else 0  # start a new span if an encompassing span ends
        old_ranks = curr_ranks
        prev_rich_text = rich_text

    return spans


def sorted_md_spans(md_spans: NDArray[np.int_]) -> Iterator[tuple[int, int, str]]:
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


def rich_texts_to_markdown(rich_texts: Sequence[RichTextBase]) -> str:
    """Convert a list of rich texts to markdown."""

    def has_only_ws_chars(text: str) -> bool:
        return re.match(r'^\s*$', text) is not None

    def first_non_ws_char(text: str) -> re.Match[str] | None:
        return re.search(r'\S', text)

    def last_non_ws_char(text: str) -> re.Match[str] | None:
        return re.search(r'\S(?=\s*$)', text)

    def add_md_style(
        md_rich_texts: list[str], rich_texts: list[RichTextBase], start: int, end: int, md_style: str
    ) -> None:
        # we skip text blocks with only whitespace characters
        if has_only_ws_chars(md_rich_texts[start]) and start != end:
            return add_md_style(md_rich_texts, rich_texts, start + 1, end, md_style)
        elif has_only_ws_chars(md_rich_texts[end]) and start != end:
            return add_md_style(md_rich_texts, rich_texts, start, end - 1, md_style)

        left = md_rich_texts[start]
        if lmatch := first_non_ws_char(left):
            if md_style == 'link':
                md_rich_texts[start] = left[: lmatch.start()] + '[' + left[lmatch.start() :]
            else:
                md_rich_texts[start] = left[: lmatch.start()] + MD_STYLE_MAP[md_style] + left[lmatch.start() :]

        right = md_rich_texts[end]
        if rmatch := last_non_ws_char(right):
            if md_style == 'link':
                link = rich_texts[end].obj_ref.href
                md_rich_texts[end] = right[: rmatch.end()] + f']({link})' + right[rmatch.end() :]
            else:
                md_rich_texts[end] = right[: rmatch.end()] + MD_STYLE_MAP[md_style] + right[rmatch.end() :]

        if bool(lmatch) != bool(rmatch):  # should never happen!
            rt_objs = '\n'.join(str(rt.obj_ref) for rt in rich_texts)
            msg = f'Error when inserting markdown styles into:\n{rt_objs}'
            raise ValueError(msg)

    def add_all_md_styles(md_rich_texts: list[str], rich_texts: list[RichTextBase]) -> None:
        for start, end, md_style in sorted_md_spans(md_spans(rich_texts)):
            add_md_style(md_rich_texts, rich_texts, start, end, md_style)

    def add_mentions(md_rich_texts: list[str], rich_texts: list[RichTextBase]) -> None:
        def is_mention(rt: RichTextBase) -> TypeGuard[Mention]:
            return rt.is_mention

        def is_math(rt: RichTextBase) -> TypeGuard[Math]:
            return rt.is_equation

        for idx, text in enumerate(rich_texts):
            if is_math(text):
                md_rich_texts[idx] = '$' + text.obj_ref.plain_text.strip() + '$'
            elif is_mention(text):
                obj_ref = text.obj_ref
                match text.type:
                    case 'user' | 'date':
                        md_rich_texts[idx] = f'[{obj_ref.plain_text}]()'  # @ is already included
                    case 'custom_emoji':
                        md_rich_texts[idx] = f'{obj_ref.plain_text}'  # parentheses are already included
                    case _:
                        md_rich_texts[idx] = f'↗[{obj_ref.plain_text}]({obj_ref.href})'

    def find_span(
        rich_texts: list[RichTextBase], style_cond: Callable[[RichTextBase], bool]
    ) -> Iterator[tuple[int, int]]:
        left: int | None = None
        for idx, text in enumerate(rich_texts):
            if style_cond(text) and left is None:
                left = idx
            elif not style_cond(text) and left is not None:
                yield left, idx - 1
                left = None
        if left is not None:
            yield left, len(rich_texts) - 1

    def add_underlines(md_rich_texts: list[str], rich_texts: list[RichTextBase]) -> None:
        for left, right in find_span(rich_texts, lambda rt: raise_unset(rt.obj_ref.annotations).underline):
            md_rich_texts[left] = '<u>' + md_rich_texts[left]
            md_rich_texts[right] += '</u>'

    rich_texts = list(rich_texts)
    md_rich_texts = [rich_text.obj_ref.plain_text for rich_text in rich_texts]
    add_mentions(md_rich_texts, rich_texts)
    add_all_md_styles(md_rich_texts, rich_texts)
    add_underlines(md_rich_texts, rich_texts)

    return ''.join(md_rich_texts)


def md_comment(text: str) -> str:
    """Create a markdown comment."""
    return f'<!--- {text} -->\n'


def get_md_renderer() -> Callable[[str], str]:
    """Create a markdown renderer."""

    vanilla_renderer = mistune.create_markdown(
        plugins=[
            'strikethrough',
            'url',
            'task_lists',
            'math',
            'table',
            FencedDirective(
                [
                    TableOfContents(),
                ]
            ),
        ],
        escape=False,
    )

    def md_renderer(md_str: str) -> str:
        match html := vanilla_renderer(md_str):
            case str():
                return html
            case list():
                msg = 'Cannot convert rich text to HTML, because the renderer returned a list:\n'
                msg += '\n'.join(str(elem) for elem in html)
                raise ValueError(msg)
            case _:
                msg = f'Cannot convert rich text to HTML, because the renderer returned {type(html)}'
                raise ValueError(msg)

    return md_renderer


render_md = get_md_renderer()
"""Convert Markdown to HTML."""

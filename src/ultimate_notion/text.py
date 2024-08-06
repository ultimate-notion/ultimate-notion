"""Utilities for working text, markdown & rich text in Notion."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar, cast
from urllib.parse import urlparse

import mistune
import numpy as np
import pendulum as pnd
from mistune import Markdown
from mistune.directives import FencedDirective, TableOfContents

from ultimate_notion.core import Wrapper
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.enums import Color
from ultimate_notion.user import User
from ultimate_notion.utils import flatten, rank

if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.page import Page

MAX_TEXT_OBJECT_SIZE = 2000
"""The max text size according to the Notion API is 2000 characters."""


MD_STYLES = ('bold', 'italic', 'strikethrough', 'code', 'link')
"""Markdown styles supported by Notion."""
MD_STYLE_MAP = {
    'bold': '**',
    'italic': '*',
    'strikethrough': '~~',
    'code': '`',
}
"""Mapping from markdown style to markdown symbol."""


T = TypeVar('T', bound=objs.RichTextBaseObject)


class RichTextBase(Wrapper[T], wraps=objs.RichTextBaseObject):
    """Super class for text, equation and mentions of various kinds."""

    @property
    def is_text(self) -> bool:
        return isinstance(self, Text)

    @property
    def is_equation(self) -> bool:
        return isinstance(self, Math)

    @property
    def is_mention(self) -> bool:
        return isinstance(self, Mention)

    def __add__(self, other: RichTextBase | RichText | str) -> RichText:
        if isinstance(other, RichTextBase):
            return RichText.wrap_obj_ref([self.obj_ref, other.obj_ref])
        elif isinstance(other, RichText):
            return RichText.wrap_obj_ref([self.obj_ref, *other.obj_ref])
        elif isinstance(other, str):
            return RichText.wrap_obj_ref([self.obj_ref, Text(other).obj_ref])
        else:
            msg = f'Cannot concatenate {type(other)} to construct a RichText object.'
            raise RuntimeError(msg)


class Text(RichTextBase[objs.TextObject], wraps=objs.TextObject):
    """A Text object.

    !!! note

        Use `RichText` instead for longer texts with complex formatting.
    """

    def __init__(
        self,
        text: str,
        *,
        bold: bool = False,
        italic: bool = False,
        strikethrough: bool = False,
        code: bool = False,
        underline: bool = False,
        color: Color = Color.DEFAULT,
        href: str | None = None,
    ):
        if len(text) > MAX_TEXT_OBJECT_SIZE:
            msg = f'Text object exceeds the maximum size of {MAX_TEXT_OBJECT_SIZE} characters. Use `RichText` instead!'
            raise ValueError(msg)

        annotations = objs.Annotations(
            bold=bold, italic=italic, strikethrough=strikethrough, code=code, underline=underline, color=color
        )
        super().__init__(text, href=href, style=annotations)


class Math(RichTextBase[objs.EquationObject], wraps=objs.EquationObject):
    """A inline equation object.

    A LaTeX equation in inline mode, e.g. `$ \\mathrm{E=mc^2} $`, but without the `$` signs.
    """

    def __init__(
        self,
        expression: str,
        *,
        bold: bool = False,
        italic: bool = False,
        strikethrough: bool = False,
        code: bool = False,
        underline: bool = False,
        color: Color = Color.DEFAULT,
        href: str | None = None,
    ):
        annotations = objs.Annotations(
            bold=bold, italic=italic, strikethrough=strikethrough, code=code, underline=underline, color=color
        )
        super().__init__(expression, href=href, style=annotations)


class Mention(RichTextBase[objs.MentionObject], wraps=objs.MentionObject):
    """A Mention object."""

    def __init__(
        self,
        target: User | Page | Database | dt.datetime | dt.date | pnd.Interval,
        *,
        bold: bool = False,
        italic: bool = False,
        strikethrough: bool = False,
        code: bool = False,
        underline: bool = False,
        color: Color = Color.DEFAULT,
    ):
        annotations = objs.Annotations(
            bold=bold, italic=italic, strikethrough=strikethrough, code=code, underline=underline, color=color
        )
        if isinstance(target, dt.datetime | dt.date | pnd.Interval):
            self.obj_ref = objs.DateRange.build(target).build_mention(style=annotations)
        else:
            self.obj_ref = target.obj_ref.build_mention(style=annotations)

    @property
    def type(self) -> str:
        """Type of the mention, e.g. user, page, etc."""
        return self.obj_ref.mention.type


class RichText(str):
    """User-facing class holding several RichTextsBase objects."""

    _rich_texts: list[RichTextBase]

    def __init__(self, plain_text: str):
        # note that super().__new__ stores the plain text in the object for `str(self)`
        super().__init__()

        rich_texts: list[RichTextBase] = []
        for part in chunky(plain_text):
            rich_texts.append(Text(part))
        self._rich_texts = rich_texts

    @classmethod
    def wrap_obj_ref(cls, obj_refs: list[objs.RichTextBaseObject] | None) -> RichText:
        obj_refs = [] if obj_refs is None else obj_refs
        rich_texts = [cast(RichTextBase, RichTextBase.wrap_obj_ref(obj_ref)) for obj_ref in obj_refs]
        plain_text = ''.join(text.obj_ref.plain_text for text in rich_texts if text)
        obj = cls(plain_text)
        obj._rich_texts = rich_texts
        return obj

    @property
    def obj_ref(self) -> list[objs.RichTextBaseObject]:
        return [elem.obj_ref for elem in self._rich_texts]

    @classmethod
    def from_markdown(cls, text: str) -> RichText:
        """Create RichTextList by parsing the markdown."""
        # ToDo: Implement me!
        # ToDo: Handle Equations and Mentions here accordingly
        raise NotImplementedError

    def to_markdown(self) -> str:
        """Convert the list of RichText objects to markdown."""
        return rich_texts_to_markdown(self._rich_texts)

    @classmethod
    def from_plain_text(cls, text: str) -> RichText:
        """Create RichTextList from plain text.

        This method is a more explicit alias for the default constructor.
        """
        return cls(text)

    def to_plain_text(self) -> str:
        """Return rich text as plaintext

        This method is a more explicit variant then just using the object.
        """
        return str(self)

    def to_html(self) -> str:
        """Return rich text as HTML."""
        return render_md(self.to_markdown())

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by Jupyter Lab automatically to display this text."""
        return self.to_html()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return str(self) == other
        elif isinstance(other, RichText):
            return str(self) == str(other)
        else:
            return NotImplemented

    def __hash__(self):
        return hash(str(self))

    def __add__(self, other: RichTextBase | RichText | str) -> RichText:
        if isinstance(other, RichTextBase):
            return RichText.wrap_obj_ref([*self.obj_ref, other.obj_ref])
        elif isinstance(other, RichText):
            return RichText.wrap_obj_ref([*self.obj_ref, *other.obj_ref])
        elif isinstance(other, str):
            return RichText.wrap_obj_ref([*self.obj_ref, Text(other).obj_ref])
        else:
            msg = f'Cannot concatenate {type(other)} to construct a RichText object.'
            raise RuntimeError(msg)


AnyText: TypeAlias = RichTextBase[Any] | RichText
"""For type hinting purposes, when working with various text types, e.g. `Text`, `RichText`, `Mention`, `Math`."""


def text_to_obj_ref(text: str | RichText | RichTextBase | list[RichTextBase]) -> list[objs.RichTextBaseObject]:
    """Convert various text representations to a list of rich text objects."""
    if isinstance(text, RichText):
        texts = text.obj_ref
    elif isinstance(text, RichTextBase):
        texts = [text.obj_ref]
    elif isinstance(text, list):
        texts = flatten([rt.obj_ref for rt in text])
    elif isinstance(text, str):
        # ToDo: Allow passing markdown text here when the markdown parser is implemented
        texts = RichText(text).obj_ref
    else:
        msg = f'Cannot convert {type(text)} to RichText objects.'
        raise ValueError(msg)
    return texts


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


def is_url(string: str) -> bool:
    """Check if a string is a valid URL."""
    try:
        result = urlparse(string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def html_img(url: str, size: float) -> str:
    """Create a img tag in HTML."""
    return f'<img src="{url}" style="height:{size:.2f}em">'


def md_spans(rich_texts: list[RichTextBase]) -> np.ndarray:
    """Convert rich text to markdown spans.

    An span is a sequence of rich texts with the same markdown style expressed as a row in the returned array.
    The value k of the j-th array column corresponds to the length of the current span richt_texts[j-k:j].
    """
    spans = np.zeros((len(MD_STYLES), len(rich_texts) + 1), dtype=int)
    old_ranks = np.zeros(len(MD_STYLES), dtype=int)
    prev_rich_text = None

    for j, rich_text in enumerate(rich_texts, start=1):
        for i, md_style in enumerate(MD_STYLES):
            if md_style == 'link':
                if not rich_text.is_text:
                    continue
                href = rich_text.obj_ref.href
                if href is not None:
                    prev_href = prev_rich_text.obj_ref.href if prev_rich_text is not None else None  # type: ignore
                    if href == prev_href:  # continue current link span or start new one
                        spans[i, j] = spans[i, j - 1] + 1
                    else:
                        spans[i, j] = 1
            else:
                annotations = rich_text.obj_ref.annotations
                if getattr(annotations, md_style) is True:
                    spans[i, j] = spans[i, j - 1] + 1

        # handle the case of overlapping spans, i.e. **abc ~~def** ghi~~ -> **abc ~~def~~** ~~ghi~~
        curr_ranks = rank(-spans[:, j])
        for i in np.where(curr_ranks < old_ranks)[0]:
            spans[i, j] = 1 if spans[i, j] > 0 else 0  # start a new span if an encompassing span ends
        old_ranks = curr_ranks
        prev_rich_text = rich_text

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
    """Convert a list of rich texts to markdown."""

    def has_only_ws_chars(text: str) -> bool:
        return re.match(r'^\s*$', text) is not None

    def first_non_ws_char(text: str) -> re.Match[str] | None:
        return re.search(r'\S', text)

    def last_non_ws_char(text: str) -> re.Match[str] | None:
        return re.search(r'\S(?=\s*$)', text)

    def add_md_style(md_rich_texts: list[str], rich_texts: list[RichTextBase], start: int, end: int, md_style: str):
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

    def add_all_md_styles(md_rich_texts: list[str], rich_texts: list[RichTextBase]):
        for start, end, md_style in sorted_md_spans(md_spans(rich_texts)):
            add_md_style(md_rich_texts, rich_texts, start, end, md_style)

    def add_mentions(md_rich_texts: list[str], rich_texts: list[RichTextBase]):
        for idx, text in enumerate(rich_texts):
            if text.is_equation:
                text = cast(Math, text)
                md_rich_texts[idx] = '$' + text.obj_ref.plain_text.strip() + '$'
            elif text.is_mention:
                text = cast(Mention, text)
                obj_ref = text.obj_ref
                match text.type:
                    case 'user' | 'date':
                        md_rich_texts[idx] = f'[{obj_ref.plain_text}]()'  # @ is already included
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

    def add_underlines(md_rich_texts: list[str], rich_texts: list[RichTextBase]):
        for left, right in find_span(rich_texts, lambda rt: rt.obj_ref.annotations.underline):
            md_rich_texts[left] = '<u>' + md_rich_texts[left]
            md_rich_texts[right] += '</u>'

    md_rich_texts = [rich_text.obj_ref.plain_text for rich_text in rich_texts]
    add_mentions(md_rich_texts, rich_texts)
    add_all_md_styles(md_rich_texts, rich_texts)
    add_underlines(md_rich_texts, rich_texts)

    return ''.join(md_rich_texts)


def md_comment(text: str) -> str:
    """Create a markdown comment."""
    return f'<!--- {text} -->\n'


def get_md_renderer() -> Markdown:
    """Create a markdown renderer."""
    return mistune.create_markdown(
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


render_md = get_md_renderer()
"""Convert Markdown to HTML."""


def join(texts: list[AnyText], *, delim: str | AnyText = ' ') -> RichText:
    """Join multiple text objects into a single text object with a given delimeter."""
    if len(texts) == 0:
        return RichText.wrap_obj_ref([])

    if isinstance(delim, str):
        delim_obj = text_to_obj_ref(delim)

    all_objs = text_to_obj_ref(texts[0])
    for text in texts[1:]:
        all_objs.extend([*delim_obj, *text_to_obj_ref(text)])

    return RichText.wrap_obj_ref(all_objs)

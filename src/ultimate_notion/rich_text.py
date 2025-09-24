"""Utilities for working with plain & rich texts in Notion."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any, TypeGuard
from urllib.parse import urlparse

import pendulum as pnd
from typing_extensions import Self, TypeVar
from url_normalize import url_normalize

from ultimate_notion.core import Wrapper
from ultimate_notion.emoji import CustomEmoji
from ultimate_notion.markdown import render_md, rich_texts_to_markdown
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.core import Unset
from ultimate_notion.obj_api.enums import Color
from ultimate_notion.obj_api.objects import MAX_TEXT_OBJECT_SIZE
from ultimate_notion.user import User

if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.page import Page


# ToDo: Use new syntax when requires-python >= 3.12
RTBO_co = TypeVar('RTBO_co', bound=objs.RichTextBaseObject, default=objs.RichTextBaseObject, covariant=True)


class RichTextBase(Wrapper[RTBO_co], wraps=objs.RichTextBaseObject):
    """Super class for text, equation and mentions of various kinds."""

    def __init__(self, *args: Any, href: str | None, **kwargs: Any) -> None:
        if href is not None:
            href = url_normalize(href)

        super().__init__(*args, href=href, **kwargs)

    @property
    def is_text(self) -> bool:
        return isinstance(self, RichText)

    @property
    def is_equation(self) -> bool:
        return isinstance(self, Math)

    @property
    def is_mention(self) -> bool:
        return isinstance(self, Mention)


class Math(RichTextBase[objs.EquationObject], wraps=objs.EquationObject):
    """An inline equation object.

    A LaTeX equation in inline mode, e.g. `$ \\mathrm{E=mc^2} $`, but without the `$` signs.

    !!! note

        Only used internally. Use the `math` function instead, to create proper `Text` object.
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
    ) -> None:
        annotations = objs.Annotations(
            bold=bold, italic=italic, strikethrough=strikethrough, code=code, underline=underline, color=color
        )
        super().__init__(expression, href=href, style=annotations)


def math(
    expression: str,
    *,
    bold: bool = False,
    italic: bool = False,
    strikethrough: bool = False,
    code: bool = False,
    underline: bool = False,
    color: Color = Color.DEFAULT,
) -> Text:
    """Create a Text that holds a formula."""
    math = Math(
        expression, bold=bold, italic=italic, strikethrough=strikethrough, code=code, underline=underline, color=color
    )
    return Text.wrap_obj_ref([math.obj_ref])


class Mention(RichTextBase[objs.MentionObject], wraps=objs.MentionObject):
    """A Mention object.

    !!! note

        Only used internally. Use the `mention` function instead, to create proper `RichText` object.
    """

    def __init__(
        self,
        target: User | Page | Database | CustomEmoji | objs.DateTimeOrRange,
        *,
        bold: bool = False,
        italic: bool = False,
        strikethrough: bool = False,
        code: bool = False,
        underline: bool = False,
        color: Color = Color.DEFAULT,
    ) -> None:
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


def mention(
    target: User | Page | Database | CustomEmoji | objs.DateTimeOrRange,
    *,
    bold: bool = False,
    italic: bool = False,
    strikethrough: bool = False,
    code: bool = False,
    underline: bool = False,
    color: Color = Color.DEFAULT,
) -> Text:
    """Create a Text that mentions another object."""
    mention = Mention(
        target, bold=bold, italic=italic, strikethrough=strikethrough, code=code, underline=underline, color=color
    )
    return Text.wrap_obj_ref([mention.obj_ref])


class RichText(RichTextBase[objs.TextObject], wraps=objs.TextObject):
    """A RichText object defining a formatted text fragment.

    !!! note

        Only used internally. Use `Text` instead.
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
        color: Color | None = None,
        href: str | None = None,
    ) -> None:
        if len(text) > MAX_TEXT_OBJECT_SIZE:
            msg = f'Text exceeds the maximum size of {MAX_TEXT_OBJECT_SIZE} characters. Use `Text` object instead!'
            raise ValueError(msg)

        color_or_unset = Unset if color is None else color
        annotations = objs.Annotations(
            bold=bold, italic=italic, strikethrough=strikethrough, code=code, underline=underline, color=color_or_unset
        )
        super().__init__(text, href=href, style=annotations)


class Text(str):
    """User-facing class holding several RichTextsBase objects.

    Rather use the constructor function `text` to create a `Text` object from a normal string with formatting.
    """

    _rich_texts: list[RichTextBase]

    def __init__(self, text: str) -> None:
        # note that super().__new__ (which is inherited) stores the plain text in the object for `str(self)`
        super().__init__()

        self._rich_texts: list[RichTextBase] = []
        if isinstance(text, Text):
            self._rich_texts = text._rich_texts
        else:
            for part in chunky(text):
                self._rich_texts.append(RichText(part))

    @property
    def rich_texts(self) -> tuple[RichTextBase, ...]:
        """Return the rich texts as immutable tuple."""
        return tuple(self._rich_texts)

    @classmethod
    def wrap_obj_ref(cls, obj_refs: list[objs.RichTextBaseObject] | None) -> Self:
        obj_refs = [] if obj_refs is None else obj_refs
        rich_texts = [RichTextBase.wrap_obj_ref(obj_ref) for obj_ref in obj_refs]
        plain_text = ''.join(text.obj_ref.plain_text for text in rich_texts if text)
        obj = cls(plain_text)
        obj._rich_texts = rich_texts
        return obj

    @property
    def obj_ref(self) -> list[objs.RichTextBaseObject]:
        return [elem.obj_ref for elem in self._rich_texts]

    @classmethod
    def from_markdown(cls, text: str) -> Text:
        """Create RichTextList by parsing the markdown."""
        # ToDo: Implement me!
        # ToDo: Handle Equations and Mentions here accordingly
        raise NotImplementedError

    def to_markdown(self) -> str:
        """Convert the list of RichText objects to markdown."""
        return rich_texts_to_markdown(self._rich_texts)

    @classmethod
    def from_plain_text(cls, text: str) -> Text:
        """Create RichTextList from plain text.

        This method is a more explicit alias for the default constructor.
        """
        return cls(text)

    def to_plain_text(self) -> str:
        """Return rich text as plain text

        This method is a more explicit variant then just using the object.
        """
        return str(self)

    @property
    def mentions(self) -> tuple[Mention, ...]:
        """Return all mentions in the text."""

        def is_mention(rt: RichTextBase) -> TypeGuard[Mention]:
            return rt.is_mention

        return tuple(rt for rt in self._rich_texts if is_mention(rt))

    def to_html(self) -> str:
        """Return rich text as HTML."""
        return render_md(self.to_markdown())

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically to display this text."""
        return self.to_html()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str | Text):
            return str(self) == str(other)
        else:
            return NotImplemented

    def __hash__(self) -> int:
        return hash(str(self))

    def __add__(self, other: str) -> Text:
        match other:
            case CustomEmoji():  # got to wrap CusomEmoji in a Mention
                return Text.wrap_obj_ref([*self.obj_ref, *mention(other).obj_ref])
            case str():
                return Text.wrap_obj_ref([*self.obj_ref, *Text(other).obj_ref])
            case _:
                msg = f'Cannot concatenate {type(other)} to construct a RichText object.'
                raise RuntimeError(msg)


def text(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    strikethrough: bool = False,
    code: bool = False,
    underline: bool = False,
    color: Color | None = None,
    href: str | None = None,
) -> Text:
    """Create a rich text Text object from a normal string with formatting.

    !!! warning

        If a `Text` object is passed, the original formatting will be lost!
    """
    if isinstance(text, Text):
        text = text.to_plain_text()

    return Text.wrap_obj_ref(
        [
            RichText(
                part,
                bold=bold,
                italic=italic,
                strikethrough=strikethrough,
                code=code,
                underline=underline,
                color=color,
                href=href,
            ).obj_ref
            for part in chunky(text)
        ]
    )


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


def join(texts: Sequence[str], *, delim: str = ' ') -> Text:
    """Join multiple str objects, including Text, into a single Text object with a given delimeter."""
    if len(texts) == 0:
        return Text.wrap_obj_ref([])

    if isinstance(delim, str):
        delim_objs = Text(delim).obj_ref

    all_objs = Text(texts[0]).obj_ref
    for text in texts[1:]:
        all_objs.extend([*delim_objs, *Text(text).obj_ref])

    return Text.wrap_obj_ref(all_objs)

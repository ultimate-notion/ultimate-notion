"""Functionality for general Notion objects like texts, files, options, etc."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar, cast

import pendulum as pnd
from emoji import emojize, is_emoji

from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.enums import Color
from ultimate_notion.text import MAX_TEXT_OBJECT_SIZE, chunky, html_img, render_md, rich_texts_to_markdown
from ultimate_notion.utils import Wrapper, flatten, get_repr, is_url

if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.page import Page


class Option(Wrapper[objs.SelectOption], wraps=objs.SelectOption):
    """Option for select & multi-select property."""

    def __init__(self, name: str, *, color: Color | str = Color.DEFAULT):
        if isinstance(color, str):
            color = Color(color)
        super().__init__(name, color=color)

    @property
    def id(self) -> str:
        """ID of the option."""
        return self.obj_ref.id

    @property
    def name(self) -> str:
        """Name of the option."""
        return self.obj_ref.name

    def description(self) -> str:
        """Description of the option."""
        if desc := self.obj_ref.description:
            return desc
        else:
            return ''

    def __repr__(self) -> str:
        return get_repr(self)

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Option):
            # We compare only the name as the id is not set for new options
            res = self.name == other.name
        elif other is None:
            res = False
        else:
            msg = f'Cannot compare Option with types {type(other)}'
            raise RuntimeError(msg)
        return res

    def __hash__(self) -> int:
        return super().__hash__()


class OptionNS:
    """Option namespace to simplify working with (Multi-)Select options."""

    @classmethod
    def to_list(cls) -> list[Option]:
        """Convert the enum to a list as needed by the (Multi)Select property types."""
        return [
            getattr(cls, var) for var in cls.__dict__ if not var.startswith('__') and not callable(getattr(cls, var))
        ]


class OptionGroup(Wrapper[objs.SelectGroup], wraps=objs.SelectGroup):
    """Group of options for status property."""

    _options: dict[str, Option]  # holds all possible options

    @classmethod
    def wrap_obj_ref(cls, obj_ref, /, *, options: list[Option] | None = None) -> OptionGroup:
        """Convienence constructor for the group of options."""
        obj = super().wrap_obj_ref(obj_ref)
        options = [] if options is None else options
        obj._options = {option.id: option for option in options}
        return obj

    @property
    def name(self) -> str:
        """Name of the option group."""
        return self.obj_ref.name

    @property
    def options(self) -> list[Option]:
        """Options within this option group."""
        return [self._options[opt_id] for opt_id in self.obj_ref.option_ids]

    def __repr__(self) -> str:
        return get_repr(self)

    def __str__(self) -> str:
        return self.name


class FileInfo(Wrapper[objs.FileObject], wraps=objs.FileObject):
    """Information about a web resource e.g. for the files property."""

    obj_ref: objs.FileObject

    def __init__(self, *, url: str, name: str | None = None) -> None:
        self.obj_ref = objs.ExternalFile.build(url=url, name=name)

    @classmethod
    def wrap_obj_ref(cls, obj_ref: objs.FileObject) -> FileInfo:
        self = cast(FileInfo, cls.__new__(cls))
        self.obj_ref = obj_ref
        return self

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return str(self) == other
        elif isinstance(other, FileInfo):
            return str(self) == str(other)
        else:
            return NotImplemented

    def __hash__(self):
        return hash(str(self))

    def __repr__(self) -> str:
        return get_repr(self)

    def __str__(self) -> str:
        return self.url

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by Jupyter Lab automatically to display this file."""
        return html_img(self.url, size=2)

    @property
    def name(self) -> str | None:
        return self.obj_ref.name

    @property
    def caption(self) -> RichText:
        return RichText.wrap_obj_ref(self.obj_ref.caption)

    @property
    def url(self) -> str:
        if isinstance(self.obj_ref, objs.HostedFile):
            return self.obj_ref.file.url
        elif isinstance(self.obj_ref, objs.ExternalFile):
            return self.obj_ref.external.url
        else:
            msg = f'Unknown file type {type(self.obj_ref)}'
            raise RuntimeError(msg)


class Emoji(Wrapper[objs.EmojiObject], str, wraps=objs.EmojiObject):
    """Emoji object which behaves like str."""

    def __init__(self, emoji: str) -> None:
        self.obj_ref = objs.EmojiObject.build(emoji)

    def __repr__(self) -> str:
        return get_repr(self)

    def __str__(self) -> str:
        return self.obj_ref.emoji

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return str(self) == other
        elif isinstance(other, Emoji):
            return str(self) == str(other)
        else:
            return NotImplemented

    def __hash__(self):
        return hash(str(self))

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by Jupyter Lab automatically to display this file."""
        return str(self)

    def to_code(self) -> str:
        """Represent the emoji as :shortcode:, e.g. :smile:"""
        raise NotImplementedError

    @classmethod
    def from_code(cls, shortcode: str) -> Emoji:
        """Create an Emoji object from a :shortcode:, e.g. :smile:"""
        raise NotImplementedError


def to_file_or_emoji(obj: FileInfo | Emoji | str) -> FileInfo | Emoji:
    """Convert the object to a FileInfo or Emoji object.

    Strings which are an emoji or describing an emoji, e.g. :thumbs_up: are converted to Emoji objects.
    Strings which are URLs are converted to FileInfo objects.
    """
    if isinstance(obj, FileInfo | Emoji):
        return obj
    elif isinstance(obj, str):
        if is_url(obj):
            return FileInfo(url=obj)
        elif is_emoji(emojized_obj := emojize(obj)):
            return Emoji(emojized_obj)
    msg = f'Cannot convert {obj} of type {type(obj)} to FileInfo or Emoji'
    raise ValueError(msg)


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
        # ToDo: Reorganise this by splitting the objects module into separate files
        from ultimate_notion.database import Database  # noqa: PLC0415
        from ultimate_notion.page import Page  # noqa: PLC0415

        annotations = objs.Annotations(
            bold=bold, italic=italic, strikethrough=strikethrough, code=code, underline=underline, color=color
        )
        if isinstance(target, User):
            self.obj_ref = objs.MentionUser.build(target.obj_ref, style=annotations)
        elif isinstance(target, Page):
            self.obj_ref = objs.MentionPage.build(target.obj_ref, style=annotations)
        elif isinstance(target, Database):
            self.obj_ref = objs.MentionDatabase.build(target.obj_ref, style=annotations)
        elif isinstance(target, dt.datetime | dt.date | pnd.Interval):
            date_range = objs.DateRange.build(target)
            self.obj_ref = objs.MentionDate.build(date_range, style=annotations)
        else:
            msg = f'Cannot create mention for {type(target)}'
            raise ValueError(msg)

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
    if isinstance(text, RichText | RichTextBase):
        texts = text.obj_ref
    elif isinstance(text, list):
        texts = flatten([rt.obj_ref for rt in text])
    elif isinstance(text, str):
        # ToDo: Allow passing markdown text here when the markdown parser is implemented
        texts = RichText(text).obj_ref
    else:
        msg = f'Cannot convert {type(text)} to RichText objects.'
        raise ValueError(msg)
    return texts


class User(Wrapper[objs.User], wraps=objs.User):
    """User object for persons and bots."""

    @classmethod
    def wrap_obj_ref(cls, obj_ref: objs.User) -> User:
        self = cast(User, cls.__new__(cls))
        self.obj_ref = obj_ref
        return self

    def __str__(self):
        return self.name

    def __repr__(self) -> str:
        return get_repr(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, User):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def id(self):
        return self.obj_ref.id

    @property
    def name(self):
        return self.obj_ref.name

    @property
    def is_person(self) -> bool:
        return isinstance(self.obj_ref, objs.Person)

    @property
    def is_bot(self) -> bool:
        return isinstance(self.obj_ref, objs.Bot)

    @property
    def is_unknown(self) -> bool:
        return isinstance(self.obj_ref, objs.UnknownUser)

    @property
    def avatar_url(self):
        return self.obj_ref.avatar_url

    @property
    def email(self) -> str | None:
        if isinstance(self.obj_ref, objs.Person):
            return self.obj_ref.person.email
        else:  # it's a bot without an e-mail
            return None


def wrap_icon(icon_obj: objs.FileObject | objs.EmojiObject | None) -> FileInfo | Emoji | None:
    """Wrap the icon object into the corresponding class."""
    if isinstance(icon_obj, objs.ExternalFile):
        return FileInfo.wrap_obj_ref(icon_obj)
    elif isinstance(icon_obj, objs.EmojiObject):
        return Emoji.wrap_obj_ref(icon_obj)
    elif icon_obj is None:
        return None
    else:
        msg = f'unknown icon object of {type(icon_obj)}'
        raise RuntimeError(msg)

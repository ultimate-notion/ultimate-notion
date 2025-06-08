"""File and emoji objects for the Notion API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar, cast
from urllib.parse import urlparse
from uuid import UUID

from emoji import demojize, emojize, is_emoji

from ultimate_notion.core import Wrapper, get_repr
from ultimate_notion.errors import InvalidAPIUsageError
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.rich_text import Text, html_img

NOTION_HOSTED_DOMAIN = 'secure.notion-static.com'


class FileInfo(Wrapper[objs.FileObject], wraps=objs.FileObject):
    """Information about a web resource e.g. for the files property."""

    obj_ref: objs.FileObject

    def __init__(self, *, url: str, name: str | None = None, caption: str | None = None) -> None:
        caption_obj = Text(caption).obj_ref if caption is not None else None  # [] is not accepted here by the API!
        if is_notion_hosted(url):
            self.obj_ref = objs.HostedFile.build(url=url, name=name, caption=caption_obj)
        else:
            self.obj_ref = objs.ExternalFile.build(url=url, name=name, caption=caption_obj)

    @classmethod
    def wrap_obj_ref(cls, obj_ref: objs.FileObject) -> FileInfo:
        self = cast(FileInfo, cls.__new__(cls))
        self.obj_ref = obj_ref
        return self

    def __eq__(self, other: object) -> bool:
        match other:
            case str():
                return str(self) == other
            case FileInfo():
                return str(self) == str(other)
            case _:
                return NotImplemented

    def __hash__(self):
        return hash(str(self))

    def __repr__(self) -> str:
        return get_repr(self)

    def __str__(self) -> str:
        return self.url

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically to display this file."""
        return html_img(self.url, size=2)

    @property
    def name(self) -> str | None:
        return self.obj_ref.name

    @name.setter
    def name(self, name: str | None) -> None:
        self.obj_ref.name = name

    @property
    def caption(self) -> Text:
        return Text.wrap_obj_ref(self.obj_ref.caption)

    @caption.setter
    def caption(self, caption: str | None) -> None:
        self.obj_ref.caption = Text(caption).obj_ref if caption is not None else []

    @property
    def url(self) -> str:
        return self.obj_ref.value.url

    @url.setter
    def url(self, url: str) -> None:
        self.obj_ref.value.url = url


TO = TypeVar('TO', bound=objs.TypedObject)


class EmojiBase(Wrapper[TO], str, ABC, wraps=objs.TypedObject):
    """Base class for emoji objects, which behave like str."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the emoji."""
        raise NotImplementedError

    @property
    def to_code(self) -> str:
        """Represent the emoji as :shortcode:, e.g. :smile:"""
        return f':{self.name}:'

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, EmojiBase | str):
            return str(self) == str(other)
        else:
            return NotImplemented

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically to display this file."""
        return str(self)


class Emoji(EmojiBase[objs.EmojiObject], wraps=objs.EmojiObject):
    """Unicode emoji object which behaves like str."""

    def __init__(self, emoji: str) -> None:
        if not is_emoji(emoji):
            emoji = emojize(emoji)
        if not is_emoji(emoji):
            msg = f'Invalid emoji string: {emoji}'
            raise ValueError(msg)
        self.obj_ref = objs.EmojiObject.build(emoji)

    @property
    def name(self) -> str:
        """Return the name of the emoji."""
        return demojize(self.obj_ref.emoji).strip(':')

    def __repr__(self) -> str:
        # we return the unicode emoji to the user for convenience in REPL
        return self.obj_ref.emoji

    def __str__(self) -> str:
        return self.obj_ref.emoji


class CustomEmoji(EmojiBase[objs.CustomEmojiObject], wraps=objs.CustomEmojiObject):
    """Custom emoji object which behaves like str."""

    def __init__(self) -> None:
        msg = 'To create a new custom emoji, go to `Settings` -> `Emoji` in Notion.'
        raise InvalidAPIUsageError(msg)

    @property
    def name(self) -> str:
        """Return the name of this custom emoji."""
        return self.obj_ref.custom_emoji.name

    @property
    def id(self) -> UUID:
        """Return the ID of this custom emoji."""
        return self.obj_ref.custom_emoji.id

    @property
    def url(self) -> str:
        """Return the URL of this custom emoji."""
        return self.obj_ref.custom_emoji.url

    def __repr__(self) -> str:
        return get_repr(self, desc=self.name)

    def __str__(self) -> str:
        return f':{self.name}:'


def wrap_icon(icon_obj: objs.FileObject | objs.EmojiObject | objs.CustomEmojiObject) -> FileInfo | CustomEmoji | Emoji:
    """Wrap the icon object into the corresponding class."""
    match icon_obj:
        case objs.ExternalFile():
            return FileInfo.wrap_obj_ref(icon_obj)
        case objs.EmojiObject():
            return Emoji.wrap_obj_ref(icon_obj)
        case objs.CustomEmojiObject():
            return CustomEmoji.wrap_obj_ref(icon_obj)
        case _:
            msg = f'unknown icon object of {type(icon_obj)}'
            raise RuntimeError(msg)


def is_notion_hosted(url: str) -> bool:
    """Check if the URL is hosted on Notion."""
    return urlparse(url).netloc == NOTION_HOSTED_DOMAIN

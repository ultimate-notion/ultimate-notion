"""File and emoji objects for the Notion API."""

from __future__ import annotations

from typing import cast

from emoji import emojize, is_emoji

from ultimate_notion.core import Wrapper, get_repr
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.text import RichText, html_img, is_url


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

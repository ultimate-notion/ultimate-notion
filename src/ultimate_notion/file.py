"""Dealing with file infos of the Notion API."""

from __future__ import annotations

from urllib.parse import urlparse

from typing_extensions import Self

from ultimate_notion.core import Wrapper, get_repr
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
    def wrap_obj_ref(cls, obj_ref: objs.FileObject) -> Self:
        """Wrap an existing low-level FileObject into a FileInfo."""
        self = cls.__new__(cls)
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

    def __hash__(self) -> int:
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
        """Return the name of the file."""
        return self.obj_ref.name

    @name.setter
    def name(self, name: str | None) -> None:
        self.obj_ref.name = name

    @property
    def caption(self) -> Text | None:
        """Return the caption of the file."""
        if (caption := self.obj_ref.caption) is None:
            return None
        return Text.wrap_obj_ref(caption)

    @caption.setter
    def caption(self, caption: str | None) -> None:
        self.obj_ref.caption = Text(caption).obj_ref if caption is not None else []

    @property
    def _type_obj(self) -> objs.HostedFile.TypeData | objs.ExternalFile.TypeData:
        """Get the low-level type data object reference."""
        match self.obj_ref:
            case objs.HostedFile():
                return self.obj_ref.file
            case objs.ExternalFile():
                return self.obj_ref.external
            case _:
                msg = f'Unknown file type: {type(self.obj_ref)}'
                raise TypeError(msg)

    @property
    def url(self) -> str:
        """Return the URL of this file."""
        return self._type_obj.url

    @url.setter
    def url(self, url: str) -> None:
        self._type_obj.url = url


def is_notion_hosted(url: str) -> bool:
    """Check if the URL is hosted on Notion."""
    return urlparse(url).netloc == NOTION_HOSTED_DOMAIN

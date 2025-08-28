"""Dealing with file infos of the Notion API."""

from __future__ import annotations

import io
from typing import BinaryIO
from urllib.parse import urlparse

import filetype
from typing_extensions import Self

from ultimate_notion.core import Wrapper, get_repr
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.rich_text import Text, html_img

NOTION_HOSTED_DOMAIN = 'secure.notion-static.com'
MAX_FILE_SIZE = 20_000_000  # 20MB in bytes


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

    @classmethod
    def from_file_upload(cls, file_upload: objs.FileUpload) -> Self:
        """Create a FileInfo from a FileUpload object.

        Args:
            file_upload: The FileUpload object from the upload API

        Returns:
            A FileInfo instance representing the uploaded file
        """
        file_obj = objs.UploadedFile.build(id=file_upload.id)
        self = cls.__new__(cls)
        self.obj_ref = file_obj
        return self

    def __eq__(self, other: object) -> bool:
        match other:
            case str() | FileInfo():
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
    def url(self) -> str | None:
        """Return the URL of this file."""
        match self.obj_ref:
            case objs.HostedFile():
                return self.obj_ref.file.url
            case objs.ExternalFile():
                return self.obj_ref.external.url
            case _:
                return None


def is_notion_hosted(url: str) -> bool:
    """Check if the URL is hosted on Notion."""
    return urlparse(url).netloc == NOTION_HOSTED_DOMAIN


def get_file_size(file: BinaryIO) -> int:
    """Get the size of a file in bytes.

    This function preserves the current file position.

    Args:
        file: The binary file object to measure

    Returns:
        The size of the file in bytes
    """
    current_pos = file.tell()
    file.seek(0, io.SEEK_END)
    file_size = file.tell()
    file.seek(current_pos)  # Reset to original position
    return file_size


def get_mime_type(file: BinaryIO) -> str:
    """Detect the MIME type of a file.

    This function preserves the current file position.

    Args:
        file: The binary file object to analyze

    Returns:
        The detected MIME type, or 'application/octet-stream' if unknown
    """
    current_pos = file.tell()
    content_sample = file.read(1024)
    file.seek(current_pos)  # Reset position

    kind = filetype.guess(content_sample)
    if kind is not None:
        return kind.mime
    else:
        # Fallback to application/octet-stream if type cannot be determined
        return 'application/octet-stream'

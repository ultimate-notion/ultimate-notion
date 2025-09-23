"""Dealing with file infos of the Notion API."""

from __future__ import annotations

import io
import time
from abc import ABC, abstractmethod
from typing import BinaryIO, cast
from urllib.parse import urlparse
from uuid import UUID

import filetype
import pendulum as pnd
from typing_extensions import Self, TypeVar
from url_normalize import url_normalize

from ultimate_notion.core import Wrapper, get_active_session, get_repr
from ultimate_notion.errors import InvalidAPIUsageError
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.core import raise_unset
from ultimate_notion.obj_api.enums import FileUploadStatus
from ultimate_notion.rich_text import Text, html_img

NOTION_HOSTED_DOMAIN = 'secure.notion-static.com'
MAX_FILE_SIZE = 20_000_000
"""Maximum file size for single part upload. It's 5MB only for the free plan"""


# ToDo: Use new syntax when requires-python >= 3.12
FO_co = TypeVar('FO_co', bound=objs.FileObject, default=objs.FileObject, covariant=True)


class AnyFile(Wrapper[FO_co], ABC, wraps=objs.FileObject):
    """Information about a web resource e.g. for the files property."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, str | AnyFile):
            return NotImplemented
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))

    @abstractmethod
    def __str__(self) -> str: ...

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


class NotionFile(AnyFile[objs.HostedFile], wraps=objs.HostedFile):
    """Information about a file that is hosted by Notion."""

    def __init__(self, *, url: str, name: str | None = None, caption: str | None = None) -> None:
        caption_obj = Text(caption).obj_ref if caption is not None else None  # [] is not accepted here by the API!
        super().__init__(url=url_normalize(url), name=name, caption=caption_obj)

    def __str__(self) -> str:
        return f'NotionFile({self.url})'

    def __repr__(self) -> str:
        return get_repr(self, desc=f'url={self.url}')

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically to display this file."""
        return html_img(self.url, size=2)

    @property
    def url(self) -> str:
        return self.obj_ref.file.url


class ExternalFile(AnyFile[objs.ExternalFile], wraps=objs.ExternalFile):
    """Information about a file that is hosted externally, i.e. not by Notion."""

    def __init__(self, *, url: str, name: str | None = None, caption: str | None = None) -> None:
        caption_obj = Text(caption).obj_ref if caption is not None else None  # [] is not accepted here by the API!
        super().__init__(url=url_normalize(url), name=name, caption=caption_obj)

    def __str__(self) -> str:
        return f'ExternalFile({self.url})'

    def __repr__(self) -> str:
        return get_repr(self, desc=f'url={self.url}')

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically to display this file."""
        return html_img(self.url, size=2)

    @property
    def url(self) -> str:
        return self.obj_ref.external.url


class UploadedFile(AnyFile[objs.UploadedFile], wraps=objs.UploadedFile):
    """Information about a file that has been uploaded to Notion.

    !!! note

        This class is used to represent files that have been uploaded to Notion.
        After it has been used, e.g. to change a cover or add a file block,
        it will be converted to a `NotionFile` (i.e. `objs.HostedFile`), when
        read again from the API.
    """

    poll_interval: float = 1.0
    obj_file_upload: objs.FileUpload

    def __init__(self) -> None:
        msg = 'Use the corresponding methods of a `Session` to get an uploaded file object.'
        raise InvalidAPIUsageError(msg)

    def __str__(self) -> str:
        return f'UploadedFile({self.id})'

    def __repr__(self) -> str:
        return get_repr(self, desc=f'id={self.id}')

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically to display this file."""
        return html_img(str(self.id), size=2)

    @property
    def id(self) -> UUID:
        """Return the ID of the uploaded file."""
        return raise_unset(self.obj_file_upload.id)

    @classmethod
    def from_file_upload(cls, file_upload: objs.FileUpload) -> Self:
        """Create an UploadedFile instance from a FileUpload object."""
        file_obj = objs.UploadedFile.build(id=file_upload.id)
        self = cls.__new__(cls)
        self.obj_ref = file_obj
        self.obj_file_upload = file_upload
        return self

    @property
    def status(self) -> FileUploadStatus:
        """Return the status of the uploaded file."""
        return self.obj_file_upload.status

    @property
    def file_name(self) -> str | None:
        """Return the file name of the uploaded file."""
        return self.obj_file_upload.filename

    @property
    def expiry_time(self) -> pnd.DateTime | None:
        """Return the expiry time of the uploaded file."""
        if expire_time := self.obj_file_upload.expiry_time:
            return pnd.instance(expire_time)
        return None

    @property
    def content_type(self) -> str | None:
        """Return the content type of the uploaded file."""
        return self.obj_file_upload.content_type

    @property
    def content_length(self) -> int | None:
        """Return the content length of the uploaded file."""
        return self.obj_file_upload.content_length

    @property
    def file_import_result(self) -> objs.FileImportSuccess | objs.FileImportError | None:
        """Return the file import result of the uploaded file."""
        if result := self.obj_file_upload.file_import_result:
            return result
        return None

    def update_status(self) -> Self:
        """Update the uploaded file information."""
        session = get_active_session()
        self.obj_file_upload = session.api.uploads.retrieve(self.id)
        return self

    def wait_until_uploaded(self) -> Self:
        """Wait until the uploaded file is fully processed."""
        while self.status != FileUploadStatus.UPLOADED:
            time.sleep(self.poll_interval)
            self.update_status()
        return self


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
        return cast(str, kind.mime)
    else:
        return 'application/octet-stream'


def url(url: str, *, name: str | None = None, caption: str | None = None) -> NotionFile | ExternalFile:
    """Create a NotionFile or ExternalFile based on the URL.

    A name and caption can be provided and will be used as default values, e.g. in a File block.
    """
    if is_notion_hosted(url):
        return NotionFile(url=url, name=name, caption=caption)
    else:
        return ExternalFile(url=url, name=name, caption=caption)

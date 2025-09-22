"""Ultimate Notion provides a pythonic, high-level API for Notion.

Notion-API: https://developers.notion.com/reference/intro
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version('ultimate-notion')
except PackageNotFoundError:  # pragma: no cover
    __version__ = 'unknown'
finally:
    del version, PackageNotFoundError

from ultimate_notion.blocks import (
    PDF,
    Audio,
    Block,
    Bookmark,
    Breadcrumb,
    BulletedItem,
    Callout,
    Code,
    Column,
    Columns,
    Divider,
    Embed,
    Equation,
    File,
    Heading1,
    Heading2,
    Heading3,
    Image,
    LinkPreview,
    LinkToPage,
    NumberedItem,
    Paragraph,
    Quote,
    SyncedBlock,
    Table,
    TableOfContents,
    TableRow,
    ToDoItem,
    ToggleItem,
    Video,
)
from ultimate_notion.core import Workspace, WorkspaceType, get_active_session
from ultimate_notion.database import Database
from ultimate_notion.emoji import Emoji
from ultimate_notion.file import AnyFile, ExternalFile, NotionFile, url
from ultimate_notion.obj_api.enums import (
    AggFunc,
    BGColor,
    CodeLang,
    Color,
    FileUploadStatus,
    NumberFormat,
    OptionGroupType,
    VState,
)
from ultimate_notion.option import Option, OptionGroup, OptionNS
from ultimate_notion.page import Page
from ultimate_notion.query import Condition, prop
from ultimate_notion.rich_text import join, math, mention, text
from ultimate_notion.schema import Property, PropType, Schema, SelfRef
from ultimate_notion.session import Session
from ultimate_notion.user import User
from ultimate_notion.utils import DateTimeOrRange, SList

__all__ = [
    'PDF',
    'AggFunc',
    'AnyFile',  # for type hinting only
    'Audio',
    'BGColor',
    'Block',  # for type hinting only
    'Bookmark',
    'Breadcrumb',
    'BulletedItem',
    'Callout',
    'Code',
    'CodeLang',
    'Color',
    'Column',
    'Columns',
    'Condition',  # for type hinting only
    'Database',
    'DateTimeOrRange',  # for type hinting only
    'Divider',
    'Embed',
    'Emoji',
    'Equation',
    'ExternalFile',
    'File',
    'FileUploadStatus',
    'Heading1',
    'Heading2',
    'Heading3',
    'Image',
    'LinkPreview',
    'LinkToPage',
    'NotionFile',
    'NumberFormat',
    'NumberedItem',
    'Option',
    'OptionGroup',
    'OptionGroupType',
    'OptionNS',
    'Page',  # for type hinting only
    'Paragraph',
    'PropType',
    'Property',  # for type hinting only
    'Quote',
    'SList',
    'Schema',
    'SelfRef',
    'Session',
    'SyncedBlock',
    'Table',
    'TableOfContents',
    'TableRow',
    'ToDoItem',
    'ToggleItem',
    'User',
    'VState',
    'Video',
    'Workspace',
    'WorkspaceType',  # for type hinting only
    '__version__',
    'get_active_session',
    'join',
    'math',
    'mention',
    'prop',
    'text',
    'url',
]

"""Ultimate Notion provides a pythonic, high-level API for Notion.

Notion-API: https://developers.notion.com/reference/intro
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version('ultimate-notion')
except PackageNotFoundError:  # pragma: no cover
    __version__ = 'unknown'
finally:
    del version, PackageNotFoundError

from ultimate_notion.blocks import (
    PDF,
    Bookmark,
    Breadcrumb,
    BulletedItem,
    Callout,
    Code,
    Column,
    ColumnList,
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
from ultimate_notion.database import Database
from ultimate_notion.obj_api.enums import AggFunc, BGColor, CodeLang, Color, NumberFormat, VState
from ultimate_notion.objects import Emoji, FileInfo, Option, OptionNS, RichText, User
from ultimate_notion.page import Page
from ultimate_notion.schema import PageSchema, Property, PropType, SelfRef
from ultimate_notion.session import Session

__all__ = [
    'PDF',
    'AggFunc',
    'BGColor',
    'Bookmark',
    'Breadcrumb',
    'BulletedItem',
    'Callout',
    'Code',
    'CodeLang',
    'Color',
    'Column',
    'ColumnList',
    'Database',
    'Divider',
    'Embed',
    'Emoji',
    'Equation',
    'File',
    'FileInfo',
    'Heading1',
    'Heading2',
    'Heading3',
    'Image',
    'LinkPreview',
    'LinkToPage',
    'NumberFormat',
    'NumberedItem',
    'Option',
    'OptionNS',
    'Page',
    'PageSchema',
    'Paragraph',
    'PropType',
    'Property',
    'Quote',
    'RichText',
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
    '__version__',
]

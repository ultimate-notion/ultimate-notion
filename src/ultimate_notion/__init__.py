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
    AnyBlock,
    Bookmark,
    Breadcrumb,
    BulletedItem,
    Callout,
    Code,
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
    ToDoItem,
    ToggleItem,
    Video,
)
from ultimate_notion.core import get_active_session
from ultimate_notion.database import Database
from ultimate_notion.file import Emoji, FileInfo
from ultimate_notion.obj_api.enums import AggFunc, BGColor, CodeLang, Color, NumberFormat, VState
from ultimate_notion.option import Option, OptionNS
from ultimate_notion.page import Page
from ultimate_notion.schema import PageSchema, Property, PropType, SelfRef
from ultimate_notion.session import Session
from ultimate_notion.text import AnyText, Math, Mention, RichText, Text, join
from ultimate_notion.user import User

__all__ = [
    'PDF',
    'AggFunc',
    'AnyBlock',  # for type hinting
    'AnyText',  # for type hinting
    'BGColor',
    'Bookmark',
    'Breadcrumb',
    'BulletedItem',
    'Callout',
    'Code',
    'CodeLang',
    'Color',
    'Columns',
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
    'Math',
    'Mention',
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
    'Text',
    'ToDoItem',
    'ToggleItem',
    'User',
    'VState',
    'Video',
    '__version__',
    'get_active_session',
    'join',
]

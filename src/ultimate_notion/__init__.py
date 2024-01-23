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

from ultimate_notion.database import Database
from ultimate_notion.obj_api.enums import AggFunc, BGColor, CodeLang, Color, NumberFormat, VState
from ultimate_notion.objects import Emoji, File, Option, OptionNS, RichText, User
from ultimate_notion.page import Page
from ultimate_notion.schema import ColType, Column, PageSchema, SelfRef
from ultimate_notion.session import Session

__all__ = [
    'AggFunc',
    'BGColor',
    'CodeLang',
    'ColType',
    'Color',
    'Column',
    'Database',
    'Emoji',
    'File',
    'NumberFormat',
    'Option',
    'OptionNS',
    'Page',
    'PageSchema',
    'RichText',
    'SelfRef',
    'Session',
    'User',
    'VState',
    '__version__',
]

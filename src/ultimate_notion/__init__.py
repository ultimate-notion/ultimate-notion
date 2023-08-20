"""Ultimate Notion provides a pythonic, high-level API for Notion

Notion-API: https://developers.notion.com/reference/intro
"""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version('ultimate-notion')
except PackageNotFoundError:  # pragma: no cover
    __version__ = 'unknown'
finally:
    del version, PackageNotFoundError

from ultimate_notion.schema import PageSchema, Column
from ultimate_notion.objects import File, Option
from ultimate_notion.session import Session

__all__ = ['__version__', 'Session', 'PageSchema', 'Column', 'File', 'Option']

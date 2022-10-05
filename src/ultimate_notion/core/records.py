"""Wrapper for Notion API data types.

These objects provide both access to the primitive data structure returned by the API
as well as higher-level access methods.  In general, attributes in lower case represent
the primitive data structure, where capitalized attributes provide higher-level access.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Union
from uuid import UUID

from .bases import NamedObject, TypedObject
from .schema import PropertyObject
from .types import EmojiObject, FileObject, PropertyValue, RichTextObject

_log = logging.getLogger(__name__)


class ParentRef(TypedObject):
    """Reference another block."""

    @classmethod
    def __compose__(cls, record):
        """Return the correct parent ID based on the object type."""

        if isinstance(record, ParentRef):
            return record

        if isinstance(record, Page):
            return PageRef(page_id=record.id)

        if isinstance(record, Database):
            return DatabaseRef(database_id=record.id)

        raise ValueError("Unrecognized 'parent' attribute")


class DatabaseRef(ParentRef, type="database_id"):
    """Reference a database."""

    database_id: UUID


class PageRef(ParentRef, type="page_id"):
    """Reference a page."""

    page_id: UUID


class BlockRef(ParentRef, type="block_id"):
    """Reference a block."""

    block_id: UUID


class WorkspaceParent(ParentRef, type="workspace"):
    """Reference the workspace."""

    workspace: bool = True


class Record(NamedObject):
    """The base type for Notion API records."""

    id: UUID = None
    created_time: datetime = None
    last_edited_time: datetime = None
    # ToDo: Check if this should be up here as Database(Record)
    #  doesn't have this property
    has_children: bool = False
    archived: bool = False
    parent: ParentRef = None
    # ToDo: is here created_by and last_edited_by missing?


class Database(Record, object="database"):
    """A database record type."""

    title: List[RichTextObject] = None
    url: str = None
    icon: Optional[Union[FileObject, EmojiObject]] = None
    cover: Optional[FileObject] = None
    properties: Dict[str, PropertyObject] = {}
    description: Optional[List[RichTextObject]] = None
    is_inline: bool = False


class Page(Record, object="page"):
    """A standard Notion page object."""

    url: str = None
    icon: Optional[Union[FileObject, EmojiObject]] = None
    cover: Optional[FileObject] = None
    properties: Dict[str, PropertyValue] = {}

    def __getitem__(self, name):
        """Indexer for the given property name.

        :param name: the name of the property to get from the internal properties
        """

        _log.debug("get property :: {%s} [%s]", self.id, name)

        if self.properties is None:
            raise AttributeError("No properties in Page")

        prop = self.properties.get(name)

        if prop is None:
            raise AttributeError(f"No such property: {name}")

        return prop

    def __setitem__(self, name, value):
        """Set the object data for the given property.

        If `value` is `None`, the property data will be deleted from the page.  This
        does not affect the schema of the page, only the contents of the property.

        :param name: the name of the property to set in the internal properties
        :param prop: the PropertyValue for the named property
        :param value: the new value for the given property
        """

        _log.debug("set property :: {%s} [%s] => %s", self.id, name, value)

        if value is None:
            self.properties.pop(name, None)

        elif not isinstance(value, PropertyValue):
            raise ValueError(f"Unable to set {name} :: unsupported value type")

        else:
            self.properties[name] = value

    # ToDo: Move this in actual Page class
    @property
    def Title(self):
        """Return the title of this page as a string.

        The title of a page is stored in its properties.  This method will examine the
        page properties, looking for the appropriate `title` entry and return as a
        string.
        """
        if self.properties is None or len(self.properties) == 0:
            return None

        for prop in self.properties.values():
            if prop.id == "title":
                return prop.Value or None

        return None

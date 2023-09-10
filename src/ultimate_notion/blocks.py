"""Core building blocks for pages and databases"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from notion_client.helpers import get_url

from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.utils import Wrapper

if TYPE_CHECKING:
    from ultimate_notion.session import Session

T = TypeVar('T')


class DataObject(Wrapper[T], wraps=obj_blocks.DataObject):
    """The base type for all data-related types, i.e, pages, databases and blocks"""

    def __init__(self, obj_ref: T):
        """Notional object reference for dispatch"""
        self.obj_ref = obj_ref

    def __eq__(self, other: object) -> bool:
        if other is None:
            return False
        elif not isinstance(other, DataObject):
            msg = f'Cannot compare {self.__class__.__name__} with {type(other).__name__}'
            raise RuntimeError(msg)
        else:
            return self.id == other.id

    @property
    def session(self) -> Session:
        """Return the currently active session"""
        from ultimate_notion.session import Session

        return Session.get_active()

    @property
    def id(self) -> UUID:  # noqa: A003
        return self.obj_ref.id

    @property
    def created_time(self) -> datetime:
        return self.obj_ref.created_time

    # ToDo: Resolve here
    @property
    def created_by(self):
        return self.obj_ref.created_by

    @property
    def last_edited_time(self) -> datetime:
        return self.obj_ref.last_edited_time

    # ToDo: Resolve here
    @property
    def last_edited_by(self):
        return self.obj_ref.last_edited_by

    @property
    def parent(self) -> DataObject | None:
        """Return the parent record or None if the workspace is the parent"""
        match (parent := self.obj_ref.parent):
            case objs.WorkspaceRef():
                return None
            case objs.PageRef():
                return self.session.get_page(page_ref=parent.page_id)
            case objs.DatabaseRef():
                return self.session.get_db(db_ref=parent.database_id)
            case objs.BlockRef():
                return self.session.get_block(block_ref=parent.block_id)
            case _:
                msg = f'Unknown parent reference {type(parent)}'
                raise RuntimeError(msg)

    @property
    def parents(self) -> tuple[DataObject, ...]:
        """Return all parents from the workspace to the actual record (excluding)"""
        match (parent := self.parent):
            case None:
                return ()
            case _:
                return (*parent.parents, parent)

    @property
    def has_children(self) -> bool:
        return self.obj_ref.has_children

    @property
    def archived(self) -> bool:
        return self.obj_ref.archived

    @property
    def url(self) -> str:
        return get_url(str(self.id))

    @property
    def properties(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'created_time': self.created_time,
            'created_by': self.created_by,
            'last_edited_time': self.last_edited_time,
            'last_edited_by': self.last_edited_by,
            'parent': self.parent,
            'has_children': self.has_children,
            'archived': self.archived,
        }


class Block(DataObject[obj_blocks.Block], wraps=obj_blocks.Block):
    pass

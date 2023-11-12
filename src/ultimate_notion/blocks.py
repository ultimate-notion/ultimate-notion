"""Core building blocks for pages and databases"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, TypeVar
from uuid import UUID

from notion_client.helpers import get_url

from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.utils import Wrapper, get_active_session

if TYPE_CHECKING:
    pass

T = TypeVar('T', bound=obj_blocks.DataObject)


class DataObject(Wrapper[T], wraps=obj_blocks.DataObject):
    """The base type for all data-related types, i.e, pages, databases and blocks"""

    def __eq__(self, other: object) -> bool:
        if other is None:
            return False
        elif not isinstance(other, DataObject):
            msg = f'Cannot compare {self.__class__.__name__} with {type(other).__name__}'
            raise RuntimeError(msg)
        else:
            return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

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
        session = get_active_session()
        parent = self.obj_ref.parent

        if isinstance(parent, objs.WorkspaceRef):
            return None
        elif isinstance(parent, objs.PageRef):
            return session.get_page(page_ref=parent.page_id)
        elif isinstance(parent, objs.DatabaseRef):
            return session.get_db(db_ref=parent.database_id)
        elif isinstance(parent, objs.BlockRef):
            return session.get_block(block_ref=parent.block_id)
        else:
            msg = f'Unknown parent reference {type(parent)}'
            raise RuntimeError(msg)

    @property
    def parents(self) -> tuple[DataObject, ...]:
        """Return all parents from the workspace to the actual record (excluding)"""
        match parent := self.parent:
            case None:
                return ()
            case _:
                return (*parent.parents, parent)

    @property
    def has_children(self) -> bool:
        return self.obj_ref.has_children

    @property
    def is_deleted(self) -> bool:
        """Return wether the object is deleted/archived"""
        return self.obj_ref.archived

    @property
    def url(self) -> str:
        return get_url(str(self.id))


class Block(DataObject[obj_blocks.Block], wraps=obj_blocks.Block):
    """Notion block object"""

    # ToDo: Implement me!

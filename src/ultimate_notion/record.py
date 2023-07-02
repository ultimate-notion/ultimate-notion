"""Core building blocks for pages and databases"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from notion_client.helpers import get_url

from ultimate_notion.obj_api import blocks, types

if TYPE_CHECKING:
    from ultimate_notion.session import Session


class Record:
    """The base type for all Notion objects."""

    obj_ref: blocks.DataRecord

    # Todo: Implement here some singleton principle so that getting the same page results in just looking up the record.

    def __init__(self, obj_ref):
        """Notional object reference for dispatch"""
        self.obj_ref = obj_ref

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Record):
            raise RuntimeError(f"Cannot compare a Record with {type(other)}")
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

    @property
    def created_by(self):
        return self.obj_ref.created_by

    @property
    def last_edited_time(self) -> datetime:
        return self.obj_ref.last_edited_time

    @property
    def last_edited_by(self):
        return self.obj_ref.last_edited_by

    @property
    def parent(self) -> Record | None:
        """Return the parent record or None if the workspace is the parent"""
        match (parent := self.obj_ref.parent):
            case types.WorkspaceRef():
                return None
            case types.PageRef():
                return self.session.get_page(page_ref=parent.page_id)
            case types.DatabaseRef():
                return self.session.get_db(db_ref=parent.database_id)
            case types.BlockRef():
                return self.session.get_block(block_ref=parent.block_id)
            case _:
                msg = f'Unknown parent reference {type(parent)}'
                raise RuntimeError(msg)

    @property
    def parents(self) -> tuple[Record, ...]:
        """Return all parents from the workspace to the actual record (excluding)"""
        match (parent := self.parent):
            case None:
                return ()
            case _:
                return parent.parents + (parent,)

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

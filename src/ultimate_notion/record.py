"""Core building block is a Record"""
from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from notion_client.helpers import get_url
from notional import blocks, types


class Record:
    """The base type for all Notion objects."""

    obj_ref: blocks.DataRecord = None

    @property
    def id(self) -> UUID:
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
    def parent(self) -> types.ParentRef:
        # ToDo: Resolve page when calling?
        return self.obj_ref.parent

    @property
    def has_children(self) -> bool:
        return self.obj_ref.has_children

    @property
    def archived(self) -> bool:
        return self.obj_ref.archived

    @property
    def url(self) -> str:
        return get_url(str(self.id))

    def to_dict(self) -> Dict[str, Any]:
        return dict(
            id=self.id,
            created_time=self.created_time,
            created_by=self.created_by,
            last_edited_time=self.last_edited_time,
            last_edited_by=self.last_edited_by,
            parent=self.parent,
            has_children=self.has_children,
            archived=self.archived,
        )

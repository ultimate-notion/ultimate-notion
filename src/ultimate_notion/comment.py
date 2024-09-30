"""Comments and discussions for pages, blocks, and databases."""

from __future__ import annotations

from typing import TypeVar

from ultimate_notion.blocks import DataObject
from ultimate_notion.core import NotionEntity
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs


class Comment(NotionEntity[objs.Comment], wraps=objs.Comment):
    """A comment on a page, block, or database."""


class Discussion(list[Comment]):
    """An list of comments, i.e. a discussion thread."""

    def append(self, text: str) -> None:
        return super().append(object)


DO = TypeVar('DO', bound=obj_blocks.DataObject)  # ToDo: Use new syntax when requires-python >= 3.12


class CommentMixin(DataObject[DO], wraps=obj_blocks.DataObject):
    """Mixin for objects that can have comments and discussions."""

    _comments: list[Discussion] | None = None

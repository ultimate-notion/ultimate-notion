"""Core building blocks for pages and databases."""

from __future__ import annotations

from abc import ABC
from datetime import datetime
from typing import TypeVar
from uuid import UUID

from notion_client.helpers import get_url

from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.core import TypedObject
from ultimate_notion.objects import RichText, User
from ultimate_notion.utils import ObjRefWrapper, Wrapper, get_active_session

# Todo: Move the functionality from the PyDantic types in here, i.e. the currenctly commented code
T = TypeVar('T', bound=obj_blocks.DataObject)


class DataObject(Wrapper[T], wraps=obj_blocks.DataObject):
    """The base type for all data-related types, i.e, pages, databases and blocks."""

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
    def id(self) -> UUID:
        return self.obj_ref.id

    @property
    def created_time(self) -> datetime:
        return self.obj_ref.created_time

    @property
    def created_by(self) -> User:
        session = get_active_session()
        return session.get_user(self.obj_ref.created_by.id)

    @property
    def last_edited_time(self) -> datetime:
        return self.obj_ref.last_edited_time

    @property
    def last_edited_by(self) -> User:
        session = get_active_session()
        return session.get_user(self.obj_ref.last_edited_by.id)

    @property
    def parent(self) -> DataObject | None:
        """Return the parent record or None if the workspace is the parent."""
        session = get_active_session()
        parent = self.obj_ref.parent

        if isinstance(parent, objs.WorkspaceRef):
            return None
        elif isinstance(parent, objs.PageRef):
            return session.get_page(page_ref=parent.page_id)
        elif isinstance(parent, objs.DatabaseRef):
            return session.get_db(db_ref=parent.database_id)
        elif isinstance(parent, objs.BlockRef):
            return session._get_block(block_ref=parent.block_id)
        else:
            msg = f'Unknown parent reference {type(parent)}'
            raise RuntimeError(msg)

    @property
    def ancestors(self) -> tuple[DataObject, ...]:
        """Return all ancestors from the workspace to the actual record (excluding)."""
        match parent := self.parent:
            case None:
                return ()
            case _:
                return (*parent.ancestors, parent)

    @property
    def has_children(self) -> bool:
        return self.obj_ref.has_children

    @property
    def is_deleted(self) -> bool:
        """Return wether the object is deleted/archived."""
        return self.obj_ref.archived

    @property
    def url(self) -> str:
        return get_url(str(self.id))


BT = TypeVar('BT', bound=obj_blocks.Block)  # ToDo: Use new syntax when requires-python >= 3.12


class Block(DataObject[BT], wraps=obj_blocks.Block):
    """General Notion block."""

    # ToDo: Implement me!


class TextBlock(DataObject[BT], ABC, wraps=obj_blocks.TextBlock):
    """Abstract Text block."""

    @property
    def rich_text(self) -> RichText:
        """Return the text content of this text block."""
        rich_texts = self.obj_ref.value.rich_text
        return RichText.wrap_obj_ref([] if rich_texts is None else rich_texts)


GT = TypeVar('GT', bound=TypedObject)


class ChildrenMixin(ObjRefWrapper[GT]):
    """Mixin for blocks that support children blocks."""

    @property
    def children(self) -> list[Block]:
        """Return all children."""
        nested_obj = self.obj_ref.value
        if nested_obj.children is not None:
            return [Block.wrap_obj_ref(child) for child in nested_obj.children]
        else:
            return []

    # def __iadd__(self, block):
    #     """Append the given block to the children of this parent in place."""
    #     self.append(block)
    #     return self

    # def append(self, block):
    #     """Append the given block to the children of this parent."""

    #     if block is None:
    #         raise ValueError("block cannot be None")

    #     nested = self()

    #     if nested.children is None:
    #         nested.children = []

    #     nested.children.append(block)

    #     self.has_children = True


class Paragraph(TextBlock[obj_blocks.Paragraph], ChildrenMixin[obj_blocks.Paragraph], wraps=obj_blocks.Paragraph):
    """Paragraph block."""

    # ToDo: Implement me!


class Heading1(TextBlock[obj_blocks.Heading1], wraps=obj_blocks.Heading1):
    """Heading 1 block."""

    # ToDo: Implement me!


class Heading2(TextBlock[obj_blocks.Heading2], wraps=obj_blocks.Heading2):
    """Heading 2 block."""

    # ToDo: Implement me!


class Heading3(TextBlock[obj_blocks.Heading3], wraps=obj_blocks.Heading3):
    """Heading 3 block."""

    # ToDo: Implement me!


class Quote(TextBlock[obj_blocks.Quote], ChildrenMixin, wraps=obj_blocks.Quote):
    """Quote block."""

    # ToDo: Implement me!


class Code(TextBlock[obj_blocks.Code], wraps=obj_blocks.Code):
    """Code block."""

    # ToDo: Implement me!


class Callout(TextBlock[obj_blocks.Callout], wraps=obj_blocks.Callout):
    """Callout block."""

    # ToDo: Implement me!


class BulletedItem(TextBlock[obj_blocks.BulletedListItem], ChildrenMixin, wraps=obj_blocks.BulletedListItem):
    """Bulleted list item."""

    # ToDo: Implement me!


class NumberedItem(TextBlock[obj_blocks.NumberedListItem], ChildrenMixin, wraps=obj_blocks.NumberedListItem):
    """Numbered list item."""

    # ToDo: Implement me!


class ToDoItem(TextBlock[obj_blocks.ToDo], ChildrenMixin, wraps=obj_blocks.ToDo):
    """ToDo list item."""

    # ToDo: Implement me!


class ToggleItem(TextBlock[obj_blocks.Toggle], ChildrenMixin, wraps=obj_blocks.Toggle):
    """Toggle list item."""

    # ToDo: Implement me!


class Divider(TextBlock[obj_blocks.Divider], wraps=obj_blocks.Divider):
    """Divider block."""

    # ToDo: Implement me!


class TableOfContents(Block[obj_blocks.TableOfContents], wraps=obj_blocks.TableOfContents):
    """Table of contents block."""

    # ToDo: Implement me!


class Breadcrumb(Block[obj_blocks.Breadcrumb], wraps=obj_blocks.Breadcrumb):
    """Breadcrumb block."""

    # ToDo: Implement me!


class Embed(Block[obj_blocks.Embed], wraps=obj_blocks.Embed):
    """Embed block."""

    # ToDo: Implement me!


class Bookmark(Block[obj_blocks.Bookmark], wraps=obj_blocks.Bookmark):
    """Bookmark block."""

    # ToDo: Implement me!


class LinkPreview(Block[obj_blocks.LinkPreview], wraps=obj_blocks.LinkPreview):
    """Link preview block."""

    # ToDo: Implement me!


class Equation(Block[obj_blocks.Equation], wraps=obj_blocks.Equation):
    """Equation block."""

    # ToDo: Implement me!


class File(Block[obj_blocks.File], wraps=obj_blocks.File):
    """File block."""

    # ToDo: Implement me!


class Image(Block[obj_blocks.Image], wraps=obj_blocks.Image):
    """Image block."""

    # ToDo: Implement me!


class Video(Block[obj_blocks.Video], wraps=obj_blocks.Video):
    """Video block."""

    # ToDo: Implement me!


class PDF(Block[obj_blocks.PDF], wraps=obj_blocks.PDF):
    """PDF block."""

    # ToDo: Implement me!


class ChildPage(Block[obj_blocks.ChildPage], wraps=obj_blocks.ChildPage):
    """Child page block."""

    # ToDo: Implement me!


class ChildDatabase(Block[obj_blocks.ChildDatabase], wraps=obj_blocks.ChildDatabase):
    """Child database block."""

    # ToDo: Implement me!


class Column(Block[obj_blocks.Column], ChildrenMixin, wraps=obj_blocks.Column):
    """Collumn block."""

    # ToDo: Implement me!


class ColumnList(Block[obj_blocks.ColumnList], ChildrenMixin, wraps=obj_blocks.ColumnList):
    """Column list block."""

    # ToDo: Implement me!


class TableRow(Block[obj_blocks.TableRow], wraps=obj_blocks.TableRow):
    """Table row block."""

    # ToDo: Implement me!


class Table(Block[obj_blocks.Table], ChildrenMixin, wraps=obj_blocks.Table):
    """Table block."""

    # ToDo: Implement me!


class LinkToPage(Block[obj_blocks.LinkToPage], wraps=obj_blocks.LinkToPage):
    """Link to page block."""

    # ToDo: Implement me!


class SyncedBlock(Block[obj_blocks.SyncedBlock], ChildrenMixin, wraps=obj_blocks.SyncedBlock):
    """Synced block - either original or synched."""

    @property
    def is_original(self) -> bool:
        """Is this block the original content."""
        return self.obj_ref.synced_block.synced_from is None

    @property
    def is_synched(self) -> bool:
        return not self.is_original


class Template(Block[obj_blocks.Template], ChildrenMixin, wraps=obj_blocks.Template):
    """Template block."""

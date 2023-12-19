"""Core building blocks for pages and databases."""

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


class Block(DataObject[obj_blocks.Block], wraps=obj_blocks.Block):
    """General Notion block."""

    # ToDo: Implement me!


class TextBlock(DataObject[obj_blocks.TextBlock], wraps=obj_blocks.TextBlock):
    """Text block."""

    # ToDo: Implement me!


class ChildrenMixin:
    """Mixin for blocks that support children blocks."""

    # ToDo: Implement me!

    # @property
    # def __children__(self):
    #     """Provide short-hand access to the children in this block."""

    #     return self("children")

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


class Paragraph(DataObject[obj_blocks.Paragraph], ChildrenMixin, wraps=obj_blocks.Paragraph):
    """Paragraph block."""

    # ToDo: Implement me!


class Heading1(DataObject[obj_blocks.Heading1], wraps=obj_blocks.Heading1):
    """Heading 1 block."""

    # ToDo: Implement me!


class Heading2(DataObject[obj_blocks.Heading2], wraps=obj_blocks.Heading2):
    """Heading 2 block."""

    # ToDo: Implement me!


class Heading3(DataObject[obj_blocks.Heading3], wraps=obj_blocks.Heading3):
    """Heading 3 block."""

    # ToDo: Implement me!


class Quote(DataObject[obj_blocks.Quote], ChildrenMixin, wraps=obj_blocks.Quote):
    """Quote block."""

    # ToDo: Implement me!


class Code(DataObject[obj_blocks.Code], wraps=obj_blocks.Code):
    """Code block."""

    # ToDo: Implement me!


class Callout(DataObject[obj_blocks.Callout], wraps=obj_blocks.Callout):
    """Callout block."""

    # ToDo: Implement me!


class BulletedItem(DataObject[obj_blocks.BulletedListItem], ChildrenMixin, wraps=obj_blocks.BulletedListItem):
    """Bulleted list item."""

    # ToDo: Implement me!


class NumberedItem(DataObject[obj_blocks.NumberedListItem], ChildrenMixin, wraps=obj_blocks.NumberedListItem):
    """Numbered list item."""

    # ToDo: Implement me!


class ToDoItem(DataObject[obj_blocks.ToDo], ChildrenMixin, wraps=obj_blocks.ToDo):
    """ToDo list item."""

    # ToDo: Implement me!


class ToggleItem(DataObject[obj_blocks.Toggle], ChildrenMixin, wraps=obj_blocks.Toggle):
    """Toggle list item."""

    # ToDo: Implement me!


class Divider(DataObject[obj_blocks.Divider], wraps=obj_blocks.Divider):
    """Divider block."""

    # ToDo: Implement me!


class TableOfContents(DataObject[obj_blocks.TableOfContents], wraps=obj_blocks.TableOfContents):
    """Table of contents block."""

    # ToDo: Implement me!


class Breadcrumb(DataObject[obj_blocks.Breadcrumb], wraps=obj_blocks.Breadcrumb):
    """Breadcrumb block."""

    # ToDo: Implement me!


class Embed(DataObject[obj_blocks.Embed], wraps=obj_blocks.Embed):
    """Embed block."""

    # ToDo: Implement me!


class Bookmark(DataObject[obj_blocks.Bookmark], wraps=obj_blocks.Bookmark):
    """Bookmark block."""

    # ToDo: Implement me!


class LinkPreview(DataObject[obj_blocks.LinkPreview], wraps=obj_blocks.LinkPreview):
    """Link preview block."""

    # ToDo: Implement me!


class Equation(DataObject[obj_blocks.Equation], wraps=obj_blocks.Equation):
    """Equation block."""

    # ToDo: Implement me!


class File(DataObject[obj_blocks.File], wraps=obj_blocks.File):
    """File block."""

    # ToDo: Implement me!


class Image(DataObject[obj_blocks.Image], wraps=obj_blocks.Image):
    """Image block."""

    # ToDo: Implement me!


class Video(DataObject[obj_blocks.Video], wraps=obj_blocks.Video):
    """Video block."""

    # ToDo: Implement me!


class PDF(DataObject[obj_blocks.PDF], wraps=obj_blocks.PDF):
    """PDF block."""

    # ToDo: Implement me!


class ChildPage(DataObject[obj_blocks.ChildPage], wraps=obj_blocks.ChildPage):
    """Child page block."""

    # ToDo: Implement me!


class ChildDatabase(DataObject[obj_blocks.ChildDatabase], wraps=obj_blocks.ChildDatabase):
    """Child database block."""

    # ToDo: Implement me!


class Column(DataObject[obj_blocks.Column], ChildrenMixin, wraps=obj_blocks.Column):
    """Collumn block."""

    # ToDo: Implement me!


class ColumnList(DataObject[obj_blocks.ColumnList], ChildrenMixin, wraps=obj_blocks.ColumnList):
    """Column list block."""

    # ToDo: Implement me!


class TableRow(DataObject[obj_blocks.TableRow], wraps=obj_blocks.TableRow):
    """Table row block."""

    # ToDo: Implement me!


class Table(DataObject[obj_blocks.Table], ChildrenMixin, wraps=obj_blocks.Table):
    """Table block."""

    # ToDo: Implement me!


class LinkToPage(DataObject[obj_blocks.LinkToPage], wraps=obj_blocks.LinkToPage):
    """Link to page block."""

    # ToDo: Implement me!


class SyncedBlock(DataObject[obj_blocks.SyncedBlock], ChildrenMixin, wraps=obj_blocks.SyncedBlock):
    """Synced block - either original or synched."""

    @property
    def is_original(self) -> bool:
        """Is this block the original content."""
        return self.obj_ref.synced_block.synced_from is None

    @property
    def is_synched(self) -> bool:
        return not self.is_original


class Template(DataObject[obj_blocks.Template], ChildrenMixin, wraps=obj_blocks.Template):
    """Template block."""

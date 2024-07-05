"""Wrapper for Notion API blocks.

Blocks are the base for all Notion content.
"""

from __future__ import annotations

from abc import ABC
from datetime import datetime
from uuid import UUID

from pydantic import SerializeAsAny

from ultimate_notion.obj_api.core import GenericObject, NotionObject, TypedObject
from ultimate_notion.obj_api.enums import BGColor, CodeLang, Color
from ultimate_notion.obj_api.objects import (
    BlockRef,
    EmojiObject,
    FileObject,
    ParentRef,
    RichTextBaseObject,
    UserRef,
)
from ultimate_notion.obj_api.props import PropertyValue
from ultimate_notion.obj_api.schema import PropertyType


class DataObject(NotionObject):
    """The base type for all Notion API records."""

    id: UUID = None  # type: ignore

    parent: SerializeAsAny[ParentRef] = None  # type: ignore
    has_children: bool = False

    in_trash: bool = False  # used to be `archived`
    archived: bool = False  # DEPRECATED! ToDo: Remove in v1.0

    created_time: datetime = None  # type: ignore
    created_by: UserRef = None  # type: ignore

    last_edited_time: datetime = None  # type: ignore
    last_edited_by: UserRef = None  # type: ignore


class Database(DataObject, object='database'):
    """A database record type."""

    title: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
    url: str = None  # type: ignore
    public_url: str | None = None
    icon: SerializeAsAny[FileObject] | EmojiObject | None = None
    cover: SerializeAsAny[FileObject] | None = None
    properties: dict[str, PropertyType] = None  # type: ignore
    description: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
    is_inline: bool = False


class Page(DataObject, object='page'):
    """A standard Notion page object."""

    url: str = None  # type: ignore
    public_url: str | None = None
    icon: SerializeAsAny[FileObject] | EmojiObject | None = None
    cover: SerializeAsAny[FileObject] | None = None
    properties: dict[str, PropertyValue] = None  # type: ignore


class Block(DataObject, TypedObject, object='block', polymorphic_base=True):
    """A standard block object in Notion.

    Calling the block will expose the nested data in the object.
    """


class UnsupportedBlock(Block, type='unsupported'):
    """A placeholder for unsupported blocks in the API."""

    class _NestedData(GenericObject): ...

    unsupported: _NestedData | None = None


class TextBlock(Block, ABC):
    """A standard abstract text block object in Notion."""


class Paragraph(TextBlock, type='paragraph'):
    """A paragraph block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] | None = None
        color: Color | BGColor = Color.DEFAULT

    paragraph: _NestedData = _NestedData()


class _NestedHeadingData(GenericObject):
    rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
    color: Color | BGColor = Color.DEFAULT
    is_toggleable: bool = False


class Heading(TextBlock, ABC):
    """Abstract Heading block."""


class Heading1(Heading, type='heading_1'):
    """A heading_1 block in Notion."""

    heading_1: _NestedHeadingData = _NestedHeadingData()


class Heading2(Heading, type='heading_2'):
    """A heading_2 block in Notion."""

    heading_2: _NestedHeadingData = _NestedHeadingData()


class Heading3(Heading, type='heading_3'):
    """A heading_3 block in Notion."""

    heading_3: _NestedHeadingData = _NestedHeadingData()


class Quote(TextBlock, type='quote'):
    """A quote block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] | None = None
        color: Color | Color = Color.DEFAULT

    quote: _NestedData = _NestedData()


class Code(TextBlock, type='code'):
    """A code block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        caption: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        language: CodeLang = CodeLang.PLAIN_TEXT

    code: _NestedData = _NestedData()


class Callout(TextBlock, type='callout'):
    """A callout block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] | None = None
        icon: SerializeAsAny[FileObject] | EmojiObject | None = None
        color: Color | BGColor = BGColor.GRAY

    callout: _NestedData = _NestedData()


class BulletedListItem(TextBlock, type='bulleted_list_item'):
    """A bulleted list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] | None = None
        color: Color | BGColor = Color.DEFAULT

    bulleted_list_item: _NestedData = _NestedData()


class NumberedListItem(TextBlock, type='numbered_list_item'):
    """A numbered list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] | None = None
        color: Color | BGColor = Color.DEFAULT

    numbered_list_item: _NestedData = _NestedData()


class ToDo(TextBlock, type='to_do'):
    """A todo list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        checked: bool = False
        children: list[SerializeAsAny[Block]] | None = None
        color: Color | BGColor = Color.DEFAULT

    to_do: _NestedData = _NestedData()


class Toggle(TextBlock, type='toggle'):
    """A toggle list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] | None = None
        color: Color | BGColor = Color.DEFAULT

    toggle: _NestedData = _NestedData()


class Divider(Block, type='divider'):
    """A divider block in Notion."""

    class _NestedData(GenericObject): ...

    divider: _NestedData = _NestedData()


class TableOfContents(Block, type='table_of_contents'):
    """A table_of_contents block in Notion."""

    class _NestedData(GenericObject):
        color: Color | BGColor = Color.DEFAULT

    table_of_contents: _NestedData = _NestedData()


class Breadcrumb(Block, type='breadcrumb'):
    """A breadcrumb block in Notion."""

    class _NestedData(GenericObject): ...

    breadcrumb: _NestedData = _NestedData()


class Embed(Block, type='embed'):
    """An embed block in Notion."""

    class _NestedData(GenericObject):
        url: str = None  # type: ignore
        caption: list[SerializeAsAny[RichTextBaseObject]] | None = None

    embed: _NestedData = _NestedData()


class Bookmark(Block, type='bookmark'):
    """A bookmark block in Notion."""

    class _NestedData(GenericObject):
        url: str = None  # type: ignore
        caption: list[SerializeAsAny[RichTextBaseObject]] | None = None

    bookmark: _NestedData = _NestedData()


class LinkPreview(Block, type='link_preview'):
    """A link_preview block in Notion."""

    class _NestedData(GenericObject):
        url: str = None  # type: ignore

    link_preview: _NestedData = _NestedData()


class Equation(Block, type='equation'):
    """An equation block in Notion."""

    class _NestedData(GenericObject):
        expression: str | None = None

    equation: _NestedData = _NestedData()


class FileBase(Block, ABC):
    """A abstract block referencing a FileObject."""


class File(FileBase, type='file'):
    """A file block in Notion."""

    file: SerializeAsAny[FileObject] = None  # type: ignore


class Image(FileBase, type='image'):
    """An image block in Notion."""

    image: SerializeAsAny[FileObject] = None  # type: ignore


class Video(FileBase, type='video'):
    """A video block in Notion."""

    video: SerializeAsAny[FileObject] = None  # type: ignore


class PDF(FileBase, type='pdf'):
    """A pdf block in Notion."""

    pdf: SerializeAsAny[FileObject] = None  # type: ignore


class ChildPage(Block, type='child_page'):
    """A child page block in Notion."""

    class _NestedData(GenericObject):
        title: str = None  # type: ignore

    child_page: _NestedData = _NestedData()


class ChildDatabase(Block, type='child_database'):
    """A child database block in Notion."""

    class _NestedData(GenericObject):
        title: str = None  # type: ignore

    child_database: _NestedData = _NestedData()


class Column(Block, type='column'):
    """A column block in Notion."""

    class _NestedData(GenericObject):
        # note that children will not be populated when getting this block
        # https://developers.notion.com/changelog/column-list-and-column-support
        children: list[SerializeAsAny[Block]] | None = None

    column: _NestedData = _NestedData()


class ColumnList(Block, type='column_list'):
    """A column list block in Notion."""

    class _NestedData(GenericObject):
        # note that children will not be populated when getting this block
        # https://developers.notion.com/changelog/column-list-and-column-support
        children: list[Column] | None = None

    column_list: _NestedData = _NestedData()


class TableRow(Block, type='table_row'):
    """A table_row block in Notion."""

    class _NestedData(GenericObject):
        cells: list[list[SerializeAsAny[RichTextBaseObject]]] | None = None

    table_row: _NestedData = _NestedData()


class Table(Block, type='table'):
    """A table block in Notion."""

    class _NestedData(GenericObject):
        table_width: int = 0
        has_column_header: bool = False
        has_row_header: bool = False

        # note that children will not be populated when getting this block
        # https://developers.notion.com/reference/block#table-blocks
        children: list[TableRow] | None = None

    table: _NestedData = _NestedData()


class LinkToPage(Block, type='link_to_page'):
    """A link_to_page block in Notion."""

    link_to_page: SerializeAsAny[ParentRef] = None  # type: ignore


class SyncedBlock(Block, type='synced_block'):
    """A synced_block block in Notion - either original or synced."""

    class _NestedData(GenericObject):
        synced_from: BlockRef | None = None
        children: list[SerializeAsAny[Block]] | None = None

    synced_block: _NestedData = _NestedData()


class Template(Block, type='template'):
    """A template block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] | None = None
        children: list[SerializeAsAny[Block]] | None = None

    template: _NestedData = _NestedData()

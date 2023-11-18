"""Wrapper for Notion API blocks.

Blocks are the base for all Notion content.
"""

from __future__ import annotations

from abc import ABC
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import SerializeAsAny

from ultimate_notion.obj_api.core import GenericObject, NotionObject, TypedObject
from ultimate_notion.obj_api.enums import BGColor, CodeLang, Color
from ultimate_notion.obj_api.objects import (
    BlockRef,
    EmojiObject,
    FileObject,
    ParentRef,
    RichTextObject,
    UserRef,
)
from ultimate_notion.obj_api.props import PropertyValue
from ultimate_notion.obj_api.schema import PropertyType


class DataObject(NotionObject):
    """The base type for all Notion API records."""

    id: UUID = None  # type: ignore  # noqa: A003

    parent: SerializeAsAny[ParentRef] = None
    has_children: bool = False

    archived: bool = False

    created_time: datetime = None  # type: ignore
    created_by: UserRef = None  # type: ignore

    last_edited_time: datetime = None  # type: ignore
    last_edited_by: UserRef = None  # type: ignore


class Database(DataObject, object='database'):
    """A database record type."""

    title: list[RichTextObject] = None  # type: ignore
    url: str = None  # type: ignore
    public_url: str | None = None
    icon: SerializeAsAny[FileObject] | EmojiObject | None = None
    cover: FileObject | None = None
    properties: dict[str, PropertyType] = None  # type: ignore
    description: list[RichTextObject] = None  # type: ignore
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

    class _NestedData(GenericObject):
        pass

    unsupported: _NestedData | None = None


class TextBlock(Block, ABC):
    """A standard abstract text block object in Notion."""

    # text blocks have a nested object with 'type' name and a 'rich_text' child

    # @property
    # def __text__(self):
    #     """Provide shorthand access to the nested text content in this block."""

    #     return self("rich_text")

    # @classmethod
    # def build(cls, *text):
    #     """Compose a `TextBlock` from the given text items."""

    #     obj = cls()
    #     obj.concat(*text)

    #     return obj

    # def concat(self, *text):
    #     """Concatenate text (either `RichTextObject` or `str` items) to this block."""

    #     rtf = rich_text(*text)

    #     # calling the block returns the nested data...  this helps deal with
    #     # sublcasses of `TextBlock` that each have different "type" attributes
    #     nested = self()
    #     nested.rich_text.extend(rtf)

    # @property
    # def PlainText(self):
    #     """Return the contents of this Block as plain text."""

    #     content = self.__text__

    #     return None if content is None else plain_text(*content)


class WithChildrenMixin:
    """Mixin for blocks that support children blocks."""

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


class Paragraph(TextBlock, WithChildrenMixin, type='paragraph'):
    """A paragraph block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] = None  # type: ignore
        children: list[Block] | None = None
        color: Color | BGColor = Color.DEFAULT

    paragraph: _NestedData = _NestedData()

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     if self.paragraph and self.paragraph.rich_text:
    #         return markdown(*self.paragraph.rich_text)

    #     return ""


class Heading1(TextBlock, type='heading_1'):
    """A heading_1 block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] = None  # type: ignore
        color: Color | BGColor = Color.DEFAULT

    heading_1: _NestedData = _NestedData()

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     if self.heading_1 and self.heading_1.rich_text:
    #         return f"# {markdown(*self.heading_1.rich_text)} #"

    #     return ""


class Heading2(TextBlock, type='heading_2'):
    """A heading_2 block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] = None  # type: ignore
        color: Color | BGColor = Color.DEFAULT

    heading_2: _NestedData = _NestedData()

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     if self.heading_2 and self.heading_2.rich_text:
    #         return f"## {markdown(*self.heading_2.rich_text)} ##"

    #     return ""


class Heading3(TextBlock, type='heading_3'):
    """A heading_3 block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] = None  # type: ignore
        color: Color | BGColor = Color.DEFAULT

    heading_3: _NestedData = _NestedData()

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     if self.heading_3 and self.heading_3.rich_text:
    #         return f"### {markdown(*self.heading_3.rich_text)} ###"

    #     return ""


class Quote(TextBlock, WithChildrenMixin, type='quote'):
    """A quote block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] = None  # type: ignore
        children: list[Block] | None = None
        color: Color | Color = Color.DEFAULT

    quote: _NestedData = _NestedData()

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     if self.quote and self.quote.rich_text:
    #         return "> " + markdown(*self.quote.rich_text)

    #     return ""


class Code(TextBlock, type='code'):
    """A code block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] = None  # type: ignore
        caption: list[RichTextObject] = None  # type: ignore
        language: CodeLang = CodeLang.PLAIN_TEXT

    code: _NestedData = _NestedData()

    # @classmethod
    # def build(cls, text, lang=CodingLanguage.PLAIN_TEXT):
    #     """Compose a `Code` block from the given text and language."""
    #     block = super().build(text)
    #     block.code.language = lang
    #     return block

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     lang = self.code.language.value if self.code and self.code.language else ""

    #     # FIXME this is not the standard way to represent code blocks in markdown...

    #     if self.code and self.code.rich_text:
    #         return f"```{lang}\n{markdown(*self.code.rich_text)}\n```"

    #     return ""


class Callout(TextBlock, WithChildrenMixin, type='callout'):
    """A callout block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] = None  # type: ignore
        children: list[Block] | None = None
        icon: SerializeAsAny[FileObject] | EmojiObject | None = None
        color: Color | BGColor = BGColor.GRAY

    callout: _NestedData = _NestedData()

    # @classmethod
    # def build(cls, text, emoji=None, color=FullColor.GRAY_BACKGROUND):
    #     """Compose a `Callout` block from the given text, emoji and color."""

    #     if emoji is not None:
    #         emoji = EmojiObject[emoji]

    #     nested = Callout._NestedData(icon=emoji, color=color)

    #     callout = cls(callout=nested)
    #     callout.concat(text)

    #     return callout


class BulletedListItem(TextBlock, WithChildrenMixin, type='bulleted_list_item'):
    """A bulleted list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] = None  # type: ignore
        children: list[Block] | None = None
        color: Color | BGColor = Color.DEFAULT

    bulleted_list_item: _NestedData = _NestedData()

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     if self.bulleted_list_item and self.bulleted_list_item.rich_text:
    #         return f"- {markdown(*self.bulleted_list_item.rich_text)}"

    #     return ""


class NumberedListItem(TextBlock, WithChildrenMixin, type='numbered_list_item'):
    """A numbered list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] = None  # type: ignore
        children: list[Block] | None = None
        color: Color | BGColor = Color.DEFAULT

    numbered_list_item: _NestedData = _NestedData()

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     if self.numbered_list_item and self.numbered_list_item.rich_text:
    #         return f"1. {markdown(*self.numbered_list_item.rich_text)}"

    #     return ""


class ToDo(TextBlock, WithChildrenMixin, type='to_do'):
    """A todo list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] = None  # type: ignore
        checked: bool = False
        children: list[Block] | None = None
        color: Color | BGColor = Color.DEFAULT

    to_do: _NestedData = _NestedData()

    # @classmethod
    # def build(cls, text, checked=False, href=None):
    #     """Compose a ToDo block from the given text and checked state."""
    #     return ToDo(
    #         to_do=ToDo._NestedData(
    #             rich_text=[TextObject[text, href]],
    #             checked=checked,
    #         )
    #     )

    # @property
    # def IsChecked(self):
    #     """Determine if this ToDo is marked as checked or not.

    #     If the block is empty (e.g. no nested data), this method returns `None`.
    #     """
    #     return self.to_do.checked if self.to_do else None

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     if self.to_do and self.to_do.rich_text:
    #         if self.to_do.checked:
    #             return f"- [x] {markdown(*self.to_do.rich_text)}"

    #         return f"- [ ] {markdown(*self.to_do.rich_text)}"

    #     return ""


class Toggle(TextBlock, WithChildrenMixin, type='toggle'):
    """A toggle list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] = None  # type: ignore
        children: list[Block] | None = None
        color: Color | BGColor = Color.DEFAULT

    toggle: _NestedData = _NestedData()


class Divider(Block, type='divider'):
    """A divider block in Notion."""

    divider: Any = None

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""
    #     return "---"


class TableOfContents(Block, type='table_of_contents'):
    """A table_of_contents block in Notion."""

    class _NestedData(GenericObject):
        color: Color | BGColor = Color.DEFAULT

    table_of_contents: _NestedData = _NestedData()


class Breadcrumb(Block, type='breadcrumb'):
    """A breadcrumb block in Notion."""

    class _NestedData(GenericObject):
        pass

    breadcrumb: _NestedData = _NestedData()


class Embed(Block, type='embed'):
    """An embed block in Notion."""

    class _NestedData(GenericObject):
        url: str = None  # type: ignore

    embed: _NestedData = _NestedData()

    # @classmethod
    # def build(cls, url):
    #     """Create a new `Embed` block from the given URL."""
    #     return Embed(embed=Embed._NestedData(url=url))

    # @property
    # def URL(self):
    #     """Return the URL contained in this `Embed` block."""
    #     return self.embed.url

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     if self.embed and self.embed.url:
    #         return f"<{self.embed.url}>"

    #     return ""


class Bookmark(Block, type='bookmark'):
    """A bookmark block in Notion."""

    class _NestedData(GenericObject):
        url: str = None  # type: ignore
        caption: list[RichTextObject] | None = None

    bookmark: _NestedData = _NestedData()

    # @classmethod
    # def build(cls, url):
    #     """Compose a new `Bookmark` block from a specific URL."""
    #     return Bookmark(bookmark=Bookmark._NestedData(url=url))

    # @property
    # def URL(self):
    #     """Return the URL contained in this `Bookmark` block."""
    #     return self.bookmark.url

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     if self.bookmark and self.bookmark.url:
    #         return f"<{self.bookmark.url}>"

    #     return ""


class LinkPreview(Block, type='link_preview'):
    """A link_preview block in Notion."""

    class _NestedData(GenericObject):
        url: str = None  # type: ignore

    link_preview: _NestedData = _NestedData()

    # @classmethod
    # def build(cls, url):
    #     """Create a new `LinkPreview` block from the given URL."""
    #     return LinkPreview(link_preview=LinkPreview._NestedData(url=url))

    # @property
    # def URL(self):
    #     """Return the URL contained in this `LinkPreview` block."""
    #     return self.link_preview.url

    # @property
    # def Markdown(self):
    #     """Return the contents of this block as markdown text."""

    #     if self.link_preview and self.link_preview.url:
    #         return f"<{self.link_preview.url}>"

    #     return ""


class Equation(Block, type='equation'):
    """An equation block in Notion."""

    class _NestedData(GenericObject):
        expression: str = None  # type: ignore

    equation: _NestedData = _NestedData()

    # @classmethod
    # def build(cls, expr):
    #     """Create a new `Equation` block from the given expression."""
    #     return LinkPreview(equation=Equation._NestedData(expression=expr))


class File(Block, type='file'):
    """A file block in Notion."""

    file: SerializeAsAny[FileObject] = None


class Image(Block, type='image'):
    """An image block in Notion."""

    image: SerializeAsAny[FileObject] = None


class Video(Block, type='video'):
    """A video block in Notion."""

    video: SerializeAsAny[FileObject] = None


class PDF(Block, type='pdf'):
    """A pdf block in Notion."""

    pdf: SerializeAsAny[FileObject] = None


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


class Column(Block, WithChildrenMixin, type='column'):
    """A column block in Notion."""

    class _NestedData(GenericObject):
        # note that children will not be populated when getting this block
        # https://developers.notion.com/changelog/column-list-and-column-support
        children: list[Block] | None = None

    column: _NestedData = _NestedData()

    # @classmethod
    # def build(cls, *blocks):
    #     """Create a new `Column` block with the given blocks as children."""
    #     col = cls()

    #     for block in blocks:
    #         col.append(block)

    #     return col


class ColumnList(Block, WithChildrenMixin, type='column_list'):
    """A column list block in Notion."""

    class _NestedData(GenericObject):
        # note that children will not be populated when getting this block
        # https://developers.notion.com/changelog/column-list-and-column-support
        children: list[Column] | None = None

    column_list: _NestedData = _NestedData()

    # @classmethod
    # def build(cls, *columns):
    #     """Create a new `Column` block with the given blocks as children."""
    #     cols = cls()

    #     for col in columns:
    #         cols.append(col)

    #     return cols


class TableRow(Block, type='table_row'):
    """A table_row block in Notion."""

    class _NestedData(GenericObject):
        cells: list[list[RichTextObject]] | None = None

        def __getitem__(self, col):
            """Return the cell content for the requested column.

            This will raise an `IndexError` if there are not enough columns.
            """
            if col > len(self.cells):
                raise IndexError()

            return self.cells[col]

    table_row: _NestedData = _NestedData()

    # def __getitem__(self, cell_num):
    #     """Return the cell content for the requested column."""
    #     return self.table_row[cell_num]

    # @classmethod
    # def build(cls, *cells):
    #     """Create a new `TableRow` block with the given cell contents."""
    #     row = cls()

    #     for cell in cells:
    #         row.append(cell)

    #     return row

    # def append(self, text):
    #     """Append the given text as a new cell in this `TableRow`.

    #     `text` may be a string, `RichTextObject` or a list of `RichTextObject`'s.

    #     :param text: the text content to append
    #     """
    #     if self.table_row.cells is None:
    #         self.table_row.cells = []

    #     if isinstance(text, list):
    #         self.table_row.cells.append(list)

    #     elif isinstance(text, RichTextObject):
    #         self.table_row.cells.append([text])

    #     else:
    #         rtf = TextObject[text]
    #         self.table_row.cells.append([rtf])

    # @property
    # def Width(self):
    #     """Return the width (number of cells) in this `TableRow`."""
    #     return len(self.table_row.cells) if self.table_row.cells else 0


class Table(Block, WithChildrenMixin, type='table'):
    """A table block in Notion."""

    class _NestedData(GenericObject):
        table_width: int = 0
        has_column_header: bool = False
        has_row_header: bool = False

        # note that children will not be populated when getting this block
        # https://developers.notion.com/reference/block#table-blocks
        children: list[TableRow] | None = None

    table: _NestedData = _NestedData()

    # @classmethod
    # def build(cls, *rows):
    #     """Create a new `Table` block with the given rows."""
    #     table = cls()

    #     for row in rows:
    #         table.append(row)

    #     return table

    # def append(self, block: TableRow):
    #     """Append the given row to this table.

    #     This method is only applicable when creating a new `Table` block.  In order to
    #     add rows to an existing `Table`, use the `blocks.children.append()` endpoint.

    #     When adding a row, this method will rase an exception if the width does not
    #     match the expected number of cells for existing rows in the block.
    #     """

    #     # XXX need to review whether this is applicable during update...  may need
    #     # to raise an error if the block has already been created on the server

    #     if not isinstance(block, TableRow):
    #         raise ValueError("Only TableRow may be appended to Table blocks.")

    #     if self.Width == 0:
    #         self.table.table_width = block.Width
    #     elif self.Width != block.Width:
    #         raise ValueError("Number of cells in row must match table")

    #     self.table.children.append(block)

    # @property
    # def Width(self):
    #     """Return the current width of this table."""
    #     return self.table.table_width


class LinkToPage(Block, type='link_to_page'):
    """A link_to_page block in Notion."""

    link_to_page: SerializeAsAny[ParentRef]


class SyncedBlock(Block, WithChildrenMixin, type='synced_block'):
    """A synced_block block in Notion - either original or synced."""

    class _NestedData(GenericObject):
        synced_from: BlockRef | None = None
        children: list[Block] | None = None

    synced_block: _NestedData = _NestedData()

    # @property
    # def IsOriginal(self):
    #     """Determine if this block represents the original content.

    #     If this method returns `False`, the block represents the sync'ed block.
    #     """
    #     return self.synced_block.synced_from is None


class Template(Block, WithChildrenMixin, type='template'):
    """A template block in Notion."""

    class _NestedData(GenericObject):
        rich_text: list[RichTextObject] | None = None
        children: list[Block] | None = None

    template: _NestedData = _NestedData()

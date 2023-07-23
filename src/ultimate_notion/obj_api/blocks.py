"""Wrapper for Notion API blocks.

Blocks are the base for all Notion content.
"""

from abc import ABC
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from ultimate_notion.obj_api.core import GenericObject, NotionObject, TypedObject
from ultimate_notion.obj_api.schema import PropertyObject
from ultimate_notion.obj_api.text import (
    CodingLanguage,
    FullColor,
    RichTextObject,
    TextObject,
    markdown,
    plain_text,
    rich_text,
)
from ultimate_notion.obj_api.types import BlockRef, EmojiObject, FileObject, ParentRef
from ultimate_notion.obj_api.props import PropertyValue
from ultimate_notion.obj_api.user import User


class DataRecord(NotionObject):
    """The base type for all Notion API records."""

    id: UUID = None

    parent: ParentRef = None
    has_children: bool = False

    archived: bool = False

    created_time: datetime = None
    created_by: User = None

    last_edited_time: datetime = None
    last_edited_by: User = None


class Database(DataRecord, object="database"):
    """A database record type."""

    title: List[RichTextObject] = None
    url: str = None
    icon: Optional[Union[FileObject, EmojiObject]] = None
    cover: Optional[FileObject] = None
    properties: Dict[str, PropertyObject] = {}
    description: Optional[List[RichTextObject]] = None
    is_inline: bool = False

    @property
    def Title(self):
        """Return the title of this database as plain text."""
        if self.title is None or len(self.title) == 0:
            return None

        return plain_text(*self.title)


class Page(DataRecord, object="page"):
    """A standard Notion page object."""

    url: str = None
    icon: Optional[Union[FileObject, EmojiObject]] = None
    cover: Optional[FileObject] = None
    properties: Dict[str, PropertyValue] = {}

    def __getitem__(self, name):
        """Indexer for the given property name.

        :param name: the name of the property to get from the internal properties
        """

        prop = self.properties.get(name)

        if prop is None:
            raise AttributeError(f"No such property: {name}")

        return prop

    def __setitem__(self, name, value):
        """Set the object data for the given property.

        If `value` is `None`, the property data will be deleted from the page.  This
        does not affect the schema of the page, only the contents of the property.

        :param name: the name of the property to set in the internal properties
        :param value: the new value for the given property
        """

        if value is None:
            self.properties.pop(name, None)

        elif isinstance(value, PropertyValue):
            self.properties[name] = value

        else:
            raise ValueError(f"Unable to set {name} :: unsupported value type")

    @property
    def Title(self):
        """Return the title of this page as a string.

        The title of a page is stored in its properties.  This method will examine the
        page properties, looking for the appropriate `title` entry and return as a
        string.
        """

        # the 'title' property may (or may not) be indexed by name...  especially in
        # the case of # database pages.  the only reliable way to find the title is by
        # scanning each property.

        for prop in self.properties.values():
            if prop.id == "title":
                return prop.Value

        return None


class Block(DataRecord, TypedObject, object="block"):
    """A standard block object in Notion.

    Calling the block will expose the nested data in the object.
    """


class UnsupportedBlock(Block, type="unsupported"):
    """A placeholder for unsupported blocks in the API."""

    class _NestedData(GenericObject):
        pass

    unsupported: Optional[_NestedData] = None


class TextBlock(Block, ABC):
    """A standard text block object in Notion."""

    # text blocks have a nested object with 'type' name and a 'rich_text' child

    @property
    def __text__(self):
        """Provide shorthand access to the nested text content in this block."""

        return self("rich_text")

    @classmethod
    def __compose__(cls, *text):
        """Compose a `TextBlock` from the given text items."""

        obj = cls()
        obj.concat(*text)

        return obj

    def concat(self, *text):
        """Concatenate text (either `RichTextObject` or `str` items) to this block."""

        rtf = rich_text(*text)

        # calling the block returns the nested data...  this helps deal with
        # sublcasses of `TextBlock` that each have different "type" attributes
        nested = self()
        nested.rich_text.extend(rtf)

    @property
    def PlainText(self):
        """Return the contents of this Block as plain text."""

        content = self.__text__

        return None if content is None else plain_text(*content)


class WithChildrenMixin:
    """Mixin for blocks that support children blocks."""

    @property
    def __children__(self):
        """Provide short-hand access to the children in this block."""

        return self("children")

    def __iadd__(self, block):
        """Append the given block to the children of this parent in place."""
        self.append(block)
        return self

    def append(self, block):
        """Append the given block to the children of this parent."""

        if block is None:
            raise ValueError("block cannot be None")

        nested = self()

        if nested.children is None:
            nested.children = []

        nested.children.append(block)

        self.has_children = True


class Paragraph(TextBlock, WithChildrenMixin, type="paragraph"):
    """A paragraph block in Notion."""

    class _NestedData(GenericObject):
        rich_text: List[RichTextObject] = []
        children: Optional[List[Block]] = None
        color: FullColor = FullColor.DEFAULT

    paragraph: _NestedData = _NestedData()

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        if self.paragraph and self.paragraph.rich_text:
            return markdown(*self.paragraph.rich_text)

        return ""


class Heading1(TextBlock, type="heading_1"):
    """A heading_1 block in Notion."""

    class _NestedData(GenericObject):
        rich_text: List[RichTextObject] = []
        color: FullColor = FullColor.DEFAULT

    heading_1: _NestedData = _NestedData()

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        if self.heading_1 and self.heading_1.rich_text:
            return f"# {markdown(*self.heading_1.rich_text)} #"

        return ""


class Heading2(TextBlock, type="heading_2"):
    """A heading_2 block in Notion."""

    class _NestedData(GenericObject):
        rich_text: List[RichTextObject] = []
        color: FullColor = FullColor.DEFAULT

    heading_2: _NestedData = _NestedData()

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        if self.heading_2 and self.heading_2.rich_text:
            return f"## {markdown(*self.heading_2.rich_text)} ##"

        return ""


class Heading3(TextBlock, type="heading_3"):
    """A heading_3 block in Notion."""

    class _NestedData(GenericObject):
        rich_text: List[RichTextObject] = []
        color: FullColor = FullColor.DEFAULT

    heading_3: _NestedData = _NestedData()

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        if self.heading_3 and self.heading_3.rich_text:
            return f"### {markdown(*self.heading_3.rich_text)} ###"

        return ""


class Quote(TextBlock, WithChildrenMixin, type="quote"):
    """A quote block in Notion."""

    class _NestedData(GenericObject):
        rich_text: List[RichTextObject] = []
        children: Optional[List[Block]] = None
        color: FullColor = FullColor.DEFAULT

    quote: _NestedData = _NestedData()

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        if self.quote and self.quote.rich_text:
            return "> " + markdown(*self.quote.rich_text)

        return ""


class Code(TextBlock, type="code"):
    """A code block in Notion."""

    class _NestedData(GenericObject):
        rich_text: List[RichTextObject] = []
        caption: List[RichTextObject] = []
        language: CodingLanguage = CodingLanguage.PLAIN_TEXT

    code: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, text, lang=CodingLanguage.PLAIN_TEXT):
        """Compose a `Code` block from the given text and language."""
        block = super().__compose__(text)
        block.code.language = lang
        return block

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        lang = self.code.language.value if self.code and self.code.language else ""

        # FIXME this is not the standard way to represent code blocks in markdown...

        if self.code and self.code.rich_text:
            return f"```{lang}\n{markdown(*self.code.rich_text)}\n```"

        return ""


class Callout(TextBlock, WithChildrenMixin, type="callout"):
    """A callout block in Notion."""

    class _NestedData(GenericObject):
        rich_text: List[RichTextObject] = []
        children: Optional[List[Block]] = None
        icon: Optional[Union[FileObject, EmojiObject]] = None
        color: FullColor = FullColor.GRAY_BACKGROUND

    callout: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, text, emoji=None, color=FullColor.GRAY_BACKGROUND):
        """Compose a `Callout` block from the given text, emoji and color."""

        if emoji is not None:
            emoji = EmojiObject[emoji]

        nested = Callout._NestedData(icon=emoji, color=color)

        callout = cls(callout=nested)
        callout.concat(text)

        return callout


class BulletedListItem(TextBlock, WithChildrenMixin, type="bulleted_list_item"):
    """A bulleted list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: List[RichTextObject] = []
        children: Optional[List[Block]] = None
        color: FullColor = FullColor.DEFAULT

    bulleted_list_item: _NestedData = _NestedData()

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        if self.bulleted_list_item and self.bulleted_list_item.rich_text:
            return f"- {markdown(*self.bulleted_list_item.rich_text)}"

        return ""


class NumberedListItem(TextBlock, WithChildrenMixin, type="numbered_list_item"):
    """A numbered list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: List[RichTextObject] = []
        children: Optional[List[Block]] = None
        color: FullColor = FullColor.DEFAULT

    numbered_list_item: _NestedData = _NestedData()

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        if self.numbered_list_item and self.numbered_list_item.rich_text:
            return f"1. {markdown(*self.numbered_list_item.rich_text)}"

        return ""


class ToDo(TextBlock, WithChildrenMixin, type="to_do"):
    """A todo list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: List[RichTextObject] = []
        checked: bool = False
        children: Optional[List[Block]] = None
        color: FullColor = FullColor.DEFAULT

    to_do: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, text, checked=False, href=None):
        """Compose a ToDo block from the given text and checked state."""
        return ToDo(
            to_do=ToDo._NestedData(
                rich_text=[TextObject[text, href]],
                checked=checked,
            )
        )

    @property
    def IsChecked(self):
        """Determine if this ToDo is marked as checked or not.

        If the block is empty (e.g. no nested data), this method returns `None`.
        """
        return self.to_do.checked if self.to_do else None

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        if self.to_do and self.to_do.rich_text:
            if self.to_do.checked:
                return f"- [x] {markdown(*self.to_do.rich_text)}"

            return f"- [ ] {markdown(*self.to_do.rich_text)}"

        return ""


class Toggle(TextBlock, WithChildrenMixin, type="toggle"):
    """A toggle list item in Notion."""

    class _NestedData(GenericObject):
        rich_text: List[RichTextObject] = []
        children: Optional[List[Block]] = None
        color: FullColor = FullColor.DEFAULT

    toggle: _NestedData = _NestedData()


class Divider(Block, type="divider"):
    """A divider block in Notion."""

    divider: Any = {}

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""
        return "---"


class TableOfContents(Block, type="table_of_contents"):
    """A table_of_contents block in Notion."""

    class _NestedData(GenericObject):
        color: FullColor = FullColor.DEFAULT

    table_of_contents: _NestedData = _NestedData()


class Breadcrumb(Block, type="breadcrumb"):
    """A breadcrumb block in Notion."""

    class _NestedData(GenericObject):
        pass

    breadcrumb: _NestedData = _NestedData()


class Embed(Block, type="embed"):
    """An embed block in Notion."""

    class _NestedData(GenericObject):
        url: str = None

    embed: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, url):
        """Create a new `Embed` block from the given URL."""
        return Embed(embed=Embed._NestedData(url=url))

    @property
    def URL(self):
        """Return the URL contained in this `Embed` block."""
        return self.embed.url

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        if self.embed and self.embed.url:
            return f"<{self.embed.url}>"

        return ""


class Bookmark(Block, type="bookmark"):
    """A bookmark block in Notion."""

    class _NestedData(GenericObject):
        url: str = None
        caption: Optional[List[RichTextObject]] = None

    bookmark: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, url):
        """Compose a new `Bookmark` block from a specific URL."""
        return Bookmark(bookmark=Bookmark._NestedData(url=url))

    @property
    def URL(self):
        """Return the URL contained in this `Bookmark` block."""
        return self.bookmark.url

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        if self.bookmark and self.bookmark.url:
            return f"<{self.bookmark.url}>"

        return ""


class LinkPreview(Block, type="link_preview"):
    """A link_preview block in Notion."""

    class _NestedData(GenericObject):
        url: str = None

    link_preview: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, url):
        """Create a new `LinkPreview` block from the given URL."""
        return LinkPreview(link_preview=LinkPreview._NestedData(url=url))

    @property
    def URL(self):
        """Return the URL contained in this `LinkPreview` block."""
        return self.link_preview.url

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        if self.link_preview and self.link_preview.url:
            return f"<{self.link_preview.url}>"

        return ""


class Equation(Block, type="equation"):
    """An equation block in Notion."""

    class _NestedData(GenericObject):
        expression: str = None

    equation: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, expr):
        """Create a new `Equation` block from the given expression."""
        return LinkPreview(equation=Equation._NestedData(expression=expr))


class File(Block, type="file"):
    """A file block in Notion."""

    file: FileObject = None


class Image(Block, type="image"):
    """An image block in Notion."""

    image: FileObject = None


class Video(Block, type="video"):
    """A video block in Notion."""

    video: FileObject = None


class PDF(Block, type="pdf"):
    """A pdf block in Notion."""

    pdf: FileObject = None


class ChildPage(Block, type="child_page"):
    """A child page block in Notion."""

    class _NestedData(GenericObject):
        title: str = None

    child_page: _NestedData = _NestedData()


class ChildDatabase(Block, type="child_database"):
    """A child database block in Notion."""

    class _NestedData(GenericObject):
        title: str = None

    child_database: _NestedData = _NestedData()


class Column(Block, WithChildrenMixin, type="column"):
    """A column block in Notion."""

    class _NestedData(GenericObject):
        # note that children will not be populated when getting this block
        # https://developers.notion.com/changelog/column-list-and-column-support
        children: Optional[List[Block]] = None

    column: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, *blocks):
        """Create a new `Column` block with the given blocks as children."""
        col = cls()

        for block in blocks:
            col.append(block)

        return col


class ColumnList(Block, WithChildrenMixin, type="column_list"):
    """A column list block in Notion."""

    class _NestedData(GenericObject):
        # note that children will not be populated when getting this block
        # https://developers.notion.com/changelog/column-list-and-column-support
        children: Optional[List[Column]] = None

    column_list: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, *columns):
        """Create a new `Column` block with the given blocks as children."""
        cols = cls()

        for col in columns:
            cols.append(col)

        return cols


class TableRow(Block, type="table_row"):
    """A table_row block in Notion."""

    class _NestedData(GenericObject):
        cells: List[List[RichTextObject]] = None

        def __getitem__(self, col):
            """Return the cell content for the requested column.

            This will raise an `IndexError` if there are not enough columns.
            """
            if col > len(self.cells):
                raise IndexError()

            return self.cells[col]

    table_row: _NestedData = _NestedData()

    def __getitem__(self, cell_num):
        """Return the cell content for the requested column."""
        return self.table_row[cell_num]

    @classmethod
    def __compose__(cls, *cells):
        """Create a new `TableRow` block with the given cell contents."""
        row = cls()

        for cell in cells:
            row.append(cell)

        return row

    def append(self, text):
        """Append the given text as a new cell in this `TableRow`.

        `text` may be a string, `RichTextObject` or a list of `RichTextObject`'s.

        :param text: the text content to append
        """
        if self.table_row.cells is None:
            self.table_row.cells = []

        if isinstance(text, list):
            self.table_row.cells.append(list)

        elif isinstance(text, RichTextObject):
            self.table_row.cells.append([text])

        else:
            rtf = TextObject[text]
            self.table_row.cells.append([rtf])

    @property
    def Width(self):
        """Return the width (number of cells) in this `TableRow`."""
        return len(self.table_row.cells) if self.table_row.cells else 0


class Table(Block, WithChildrenMixin, type="table"):
    """A table block in Notion."""

    class _NestedData(GenericObject):
        table_width: int = 0
        has_column_header: bool = False
        has_row_header: bool = False

        # note that children will not be populated when getting this block
        # https://developers.notion.com/reference/block#table-blocks
        children: Optional[List[TableRow]] = []

    table: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, *rows):
        """Create a new `Table` block with the given rows."""
        table = cls()

        for row in rows:
            table.append(row)

        return table

    def append(self, block: TableRow):
        """Append the given row to this table.

        This method is only applicable when creating a new `Table` block.  In order to
        add rows to an existing `Table`, use the `blocks.children.append()` endpoint.

        When adding a row, this method will rase an exception if the width does not
        match the expected number of cells for existing rows in the block.
        """

        # XXX need to review whether this is applicable during update...  may need
        # to raise an error if the block has already been created on the server

        if not isinstance(block, TableRow):
            raise ValueError("Only TableRow may be appended to Table blocks.")

        if self.Width == 0:
            self.table.table_width = block.Width
        elif self.Width != block.Width:
            raise ValueError("Number of cells in row must match table")

        self.table.children.append(block)

    @property
    def Width(self):
        """Return the current width of this table."""
        return self.table.table_width


class LinkToPage(Block, type="link_to_page"):
    """A link_to_page block in Notion."""

    link_to_page: ParentRef


class SyncedBlock(Block, WithChildrenMixin, type="synced_block"):
    """A synced_block block in Notion - either original or synced."""

    class _NestedData(GenericObject):
        synced_from: Optional[BlockRef] = None
        children: Optional[List[Block]] = None

    synced_block: _NestedData = _NestedData()

    @property
    def IsOriginal(self):
        """Determine if this block represents the original content.

        If this method returns `False`, the block represents the sync'ed block.
        """
        return self.synced_block.synced_from is None


class Template(Block, WithChildrenMixin, type="template"):
    """A template block in Notion."""

    class _NestedData(GenericObject):
        rich_text: Optional[List[RichTextObject]] = None
        children: Optional[List[Block]] = None

    template: _NestedData = _NestedData()

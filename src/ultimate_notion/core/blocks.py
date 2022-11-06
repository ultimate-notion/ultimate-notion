"""Wrapper for Notion API blocks.

Blocks are specific records that hold content.

Similar to other records, these object provide access to the primitive data structure
used in the Notion API as well as higher-level methods.
"""

import logging
from typing import Any, List, Optional, Union

from .bases import NestedObject, TypedObject
from .records import BlockRef, ParentRef, Record
from .text import CodingLanguage, FullColor, RichTextObject, TextObject, chunky, markdown, plain_text
from .types import EmojiObject, FileObject

_log = logging.getLogger(__name__)


class Block(Record, TypedObject, object="block"):
    """A standard block object in Notion.

    Calling the block will expose the nested data in the object.
    """


class UnsupportedBlock(Block, type="unsupported"):
    """A placeholder for unsupported blocks in the API."""

    class _NestedData(NestedObject):
        pass

    unsupported: Optional[_NestedData] = None


class TextBlock(Block):
    """A standard text block object in Notion."""

    # text blocks have a nested object with 'type' name and a 'text' child

    @property
    def __text__(self):
        """Provide shorthand access to the nested text content in this block."""

        return self("rich_text")

    @classmethod
    def __compose__(cls, text):
        """Compose a `TextBlock` from the given text."""

        if text is None:
            return None

        obj = cls()
        obj.concat(text)

        return obj

    def concat(self, *text):
        """Concatenate text (either `RichTextObject` or `str` items) to this block."""

        nested = self()

        if not hasattr(nested, "rich_text"):
            raise AttributeError("nested data does not contain text")

        if nested.rich_text is None:
            nested.rich_text = []

        for obj in text:
            if obj is None:
                continue

            self._append_object(obj)

    def _append_object(self, obj):
        """Append the given object to the internal text of this TextObject."""

        if isinstance(obj, RichTextObject):
            self._append_rtf(obj)

        elif isinstance(obj, str):
            self._append_text(obj)

        else:
            raise ValueError("unsupported text object")

    def _append_rtf(self, rtf):
        """Append the given RichTextObject to this TextObject."""
        nested = self()
        nested.rich_text.append(rtf)

    def _append_text(self, text):
        """Append the given text to this TextObject.

        This text will be split into chunks in accordance with the Notion API.
        """
        nested = self()

        # break up the text and compose new TextObject's from the pieces

        for chunk in chunky(text):
            obj = TextObject[chunk]
            nested.rich_text.append(obj)

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

        if not hasattr(nested, "children"):
            raise TypeError("nested data does not contain children")

        if nested.children is None:
            nested.children = []

        nested.children.append(block)

        self.has_children = True


class Paragraph(TextBlock, WithChildrenMixin, type="paragraph"):
    """A paragraph block in Notion."""

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
        rich_text: List[RichTextObject] = []
        caption: List[RichTextObject] = []
        language: CodingLanguage = CodingLanguage.PLAIN_TEXT

    code: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, text, lang=CodingLanguage.PLAIN_TEXT):
        """Compose a `Code` block from the given text and language."""
        return Code(
            code=Code._NestedData(
                rich_text=[TextObject[text]],
                language=lang,
            )
        )

    @property
    def Markdown(self):
        """Return the contents of this block as markdown text."""

        lang = self.code.language if self.code and self.code.language else ""

        # FIXME this is not the standard way to represent code blocks in markdown...

        if self.code and self.code.rich_text:
            return f"```{lang}\n{markdown(*self.code.rich_text)}\n```"

        return ""


class Callout(TextBlock, WithChildrenMixin, type="callout"):
    """A callout block in Notion."""

    class _NestedData(NestedObject):
        rich_text: List[RichTextObject] = []
        children: Optional[List[Block]] = None
        icon: Optional[Union[FileObject, EmojiObject]] = None
        color: FullColor = FullColor.DEFAULT

    callout: _NestedData = _NestedData()


class BulletedListItem(TextBlock, WithChildrenMixin, type="bulleted_list_item"):
    """A bulleted list item in Notion."""

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
        color: FullColor = FullColor.DEFAULT

    table_of_contents: _NestedData = _NestedData()


class Breadcrumb(Block, type="breadcrumb"):
    """A breadcrumb block in Notion."""

    class _NestedData(NestedObject):
        pass

    breadcrumb: _NestedData = _NestedData()


class Embed(Block, type="embed"):
    """An embed block in Notion."""

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
        title: str = None

    child_page: _NestedData = _NestedData()


class ChildDatabase(Block, type="child_database"):
    """A child database block in Notion."""

    class _NestedData(NestedObject):
        title: str = None

    child_database: _NestedData = _NestedData()


class ColumnList(Block, type="column_list"):
    """A column list block in Notion."""

    class _NestedData(NestedObject):
        pass

    column_list: _NestedData = _NestedData()


class Column(Block, type="column"):
    """A column block in Notion."""

    class _NestedData(NestedObject):
        pass

    column: _NestedData = _NestedData()


class TableRow(Block, type="table_row"):
    """A table_row block in Notion."""

    class _NestedData(NestedObject):
        cells: List[List[RichTextObject]] = None

    table_row: _NestedData = _NestedData()

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
            rtf = TextObject.from_value(text)
            self.table_row.cells.append([rtf])

    @property
    def Width(self):
        """Return the width (number of cells) in this `TableRow`."""
        return len(self.table_row.cells) if self.table_row.cells else 0


class Table(Block, WithChildrenMixin, type="table"):
    """A table block in Notion."""

    class _NestedData(NestedObject):
        table_width: int = 0
        has_column_header: bool = False
        has_row_header: bool = False

        # note that children will not be populated when getting this block
        # https://developers.notion.com/reference/block#table-blocks
        children: Optional[List[TableRow]] = []

    table: _NestedData = _NestedData()

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

    class _NestedData(NestedObject):
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

    class _NestedData(NestedObject):
        rich_text: Optional[List[RichTextObject]] = None
        children: Optional[List[Block]] = None

    template: _NestedData = _NestedData()

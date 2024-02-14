"""Core building blocks for pages and databases."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, TypeVar, cast
from uuid import UUID

from tabulate import tabulate

from ultimate_notion import objects
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.objects import RichText, User
from ultimate_notion.text import md_comment
from ultimate_notion.utils import Wrapper, get_active_session, get_url, get_uuid

if TYPE_CHECKING:
    from ultimate_notion.page import Page


# Todo: Implement the constructors for the blocks
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


BT = TypeVar('BT', bound=obj_blocks.Block)  # ToDo: Use new syntax when requires-python >= 3.12


class Block(DataObject[BT], ABC, wraps=obj_blocks.Block):
    """General Notion block."""

    @abstractmethod
    def to_markdown(self) -> str:
        """Return the content of the block as Markdown."""
        ...

    @property
    def block_url(self) -> str:
        """Return the URL of the block."""
        return get_url(self.id)


class TextBlock(Block[BT], ABC, wraps=obj_blocks.TextBlock):
    """Abstract Text block."""

    @property
    def rich_text(self) -> RichText:
        """Return the text content of this text block."""
        rich_texts = self.obj_ref.value.rich_text
        return RichText.wrap_obj_ref(rich_texts)


class ChildrenMixin(DataObject[T], wraps=obj_blocks.DataObject):
    """Mixin for blocks that support children blocks."""

    @property
    def children(self: DataObject) -> list[Block]:
        """Return all children."""
        if self.has_children:
            nested_obj = self.obj_ref.value

            if nested_obj.children is None:
                session = get_active_session()
                nested_obj.children = list(session.api.blocks.children.list(parent=get_uuid(self.obj_ref)))

            return [Block.wrap_obj_ref(child) for child in nested_obj.children]
        else:
            return []

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

    def to_markdown(self) -> str:
        return f'# {self.rich_text.to_markdown()}'


class Heading1(TextBlock[obj_blocks.Heading1], wraps=obj_blocks.Heading1):
    """Heading 1 block."""

    def to_markdown(self) -> str:
        return f'# {self.rich_text.to_markdown()}'


class Heading2(TextBlock[obj_blocks.Heading2], wraps=obj_blocks.Heading2):
    """Heading 2 block."""

    def to_markdown(self) -> str:
        return f'## {self.rich_text.to_markdown()}'


class Heading3(TextBlock[obj_blocks.Heading3], wraps=obj_blocks.Heading3):
    """Heading 3 block."""

    def to_markdown(self) -> str:
        return f'### {self.rich_text.to_markdown()}'


class Quote(TextBlock[obj_blocks.Quote], ChildrenMixin, wraps=obj_blocks.Quote):
    """Quote block."""

    def to_markdown(self) -> str:
        return f'> {self.rich_text.to_markdown()}\n'


class Code(TextBlock[obj_blocks.Code], wraps=obj_blocks.Code):
    """Code block."""

    def to_markdown(self) -> str:
        lang = self.obj_ref.code.language
        return f'```{lang}\n{self.rich_text.to_markdown()}\n```'

    @property
    def caption(self) -> RichText:
        return RichText.wrap_obj_ref(self.obj_ref.code.caption)

    # @classmethod
    # def build(cls, text, lang=CodingLanguage.PLAIN_TEXT):
    #     """Compose a `Code` block from the given text and language."""
    #     block = super().build(text)
    #     block.code.language = lang
    #     return block


class Callout(TextBlock[obj_blocks.Callout], wraps=obj_blocks.Callout):
    """Callout block."""

    @property
    def icon(self) -> objects.File | objects.Emoji | None:
        return objects.wrap_icon(self.obj_ref.callout.icon)

    def to_markdown(self) -> str:
        if isinstance(icon := self.icon, objects.Emoji):
            return f'{icon} {self.rich_text.to_markdown()}\n'
        elif isinstance(icon := self.icon, objects.File):
            return f'![icon]({icon.url}) {self.rich_text.to_markdown()}\n'
        else:
            return f'{self.rich_text.to_markdown()}\n'

    # @classmethod
    # def build(cls, text, emoji=None, color=FullColor.GRAY_BACKGROUND):
    #     """Compose a `Callout` block from the given text, emoji and color."""

    #     if emoji is not None:
    #         emoji = EmojiObject[emoji]

    #     nested = Callout._NestedData(icon=emoji, color=color)

    #     callout = cls(callout=nested)
    #     callout.concat(text)

    #     return callout


class BulletedItem(TextBlock[obj_blocks.BulletedListItem], ChildrenMixin, wraps=obj_blocks.BulletedListItem):
    """Bulleted list item."""

    def to_markdown(self) -> str:
        return f'- {self.rich_text.to_markdown()}\n'


class NumberedItem(TextBlock[obj_blocks.NumberedListItem], ChildrenMixin, wraps=obj_blocks.NumberedListItem):
    """Numbered list item."""

    def to_markdown(self) -> str:
        return f'1. {self.rich_text.to_markdown()}\n'


class ToDoItem(TextBlock[obj_blocks.ToDo], ChildrenMixin, wraps=obj_blocks.ToDo):
    """ToDo list item."""

    def is_checked(self) -> bool:
        return self.obj_ref.to_do.checked

    def to_markdown(self) -> str:
        mark = 'x' if self.is_checked() else ' '
        return f'- [{mark}] {self.rich_text.to_markdown()}\n'

    # def build(cls, text, checked=False, href=None):
    #     """Compose a ToDo block from the given text and checked state."""
    #     return ToDo(
    #         to_do=ToDo._NestedData(
    #             rich_text=[TextObject[text, href]],
    #             checked=checked,
    #         )
    #     )


class ToggleItem(TextBlock[obj_blocks.Toggle], ChildrenMixin, wraps=obj_blocks.Toggle):
    """Toggle list item."""

    def to_markdown(self) -> str:
        return f'- {self.rich_text.to_markdown()}\n'


class Divider(TextBlock[obj_blocks.Divider], wraps=obj_blocks.Divider):
    """Divider block."""

    def to_markdown(self) -> str:  # noqa: PLR6301
        return '---\n'


class TableOfContents(Block[obj_blocks.TableOfContents], wraps=obj_blocks.TableOfContents):
    """Table of contents block."""

    def to_markdown(self) -> str:  # noqa: PLR6301
        return '```{toc}\n```'


class Breadcrumb(Block[obj_blocks.Breadcrumb], wraps=obj_blocks.Breadcrumb):
    """Breadcrumb block."""

    def to_markdown(self) -> str:
        from ultimate_notion.page import Page  # noqa: PLC0415

        return ' / '.join(page.title for page in self.ancestors if isinstance(page, Page)) + '\n'


class Embed(Block[obj_blocks.Embed], wraps=obj_blocks.Embed):
    """Embed block."""

    @property
    def embed_url(self) -> str | None:
        """Return the URL of the embeded item."""
        return self.obj_ref.embed.url

    @property
    def caption(self) -> RichText:
        return RichText.wrap_obj_ref(self.obj_ref.embed.caption)

    def to_markdown(self) -> str:
        if self.embed_url is not None:
            return f'[{self.embed_url}]({self.embed_url})\n'
        else:
            return ''

    # @classmethod
    # def build(cls, url):
    #     """Create a new `Embed` block from the given URL."""
    #     return Embed(embed=Embed._NestedData(url=url))


class Bookmark(Block[obj_blocks.Bookmark], wraps=obj_blocks.Bookmark):
    """Bookmark block."""

    @property
    def url(self) -> str | None:
        """Return the URL of the bookmark."""
        return self.obj_ref.bookmark.url

    def to_markdown(self) -> str:
        if self.url is not None:
            return f'Bookmark: [{self.url}]({self.url})\n'
        else:
            return 'Bookmark: [Add a web bookmark]()\n'  # emtpy bookmark

    # @classmethod
    # def build(cls, url):
    #     """Compose a new `Bookmark` block from a specific URL."""
    #     return Bookmark(bookmark=Bookmark._NestedData(url=url))


class LinkPreview(Block[obj_blocks.LinkPreview], wraps=obj_blocks.LinkPreview):
    """Link preview block."""

    @property
    def url(self) -> str | None:
        return self.obj_ref.link_preview.url

    def to_markdown(self) -> str:
        if self.block_url is not None:
            return f'Link preview: [{self.url}]({self.url})\n'
        return super().to_markdown()

    # @classmethod
    # def build(cls, url):
    #     """Create a new `LinkPreview` block from the given URL."""
    #     return LinkPreview(link_preview=LinkPreview._NestedData(url=url))


class Equation(Block[obj_blocks.Equation], wraps=obj_blocks.Equation):
    """Equation block."""

    @property
    def expression(self) -> str:
        if (expr := self.obj_ref.equation.expression) is not None:
            return expr.rstrip()
        else:
            return ''

    def to_markdown(self) -> str:
        return f'$$\n{self.expression}\n$$\n'

    # @classmethod
    # def build(cls, expr):
    #     """Create a new `Equation` block from the given expression."""
    #     return LinkPreview(equation=Equation._NestedData(expression=expr))


FT = TypeVar('FT', bound=obj_blocks.FileObjectBlock)


class FileObjectBlock(DataObject[FT], ABC, wraps=obj_blocks.FileObjectBlock):
    """Abstract Block holding a FileObject"""

    @property
    def _file(self) -> objs.FileObject:
        if isinstance(file_obj := self.obj_ref.value, objs.FileObject):
            return file_obj
        else:
            msg = f'Unknown file type {type(file_obj)}'
            raise ValueError(msg)

    @property
    def caption(self) -> RichText:
        return RichText.wrap_obj_ref(self._file.caption)

    @property
    def url(self) -> str:
        file = self._file
        if isinstance(file, objs.ExternalFile):
            return file.external.url
        elif isinstance(file, objs.HostedFile):
            return file.file.url
        else:
            msg = f'Unknown file type {type(file)}'
            raise ValueError(msg)


class File(FileObjectBlock[obj_blocks.File], wraps=obj_blocks.File):
    """File block."""

    @property
    def name(self) -> str:
        name = self._file.name
        return name if name is not None else ''

    def to_markdown(self) -> str:
        md = f'[📎 {self.name}]({self.url})\n'
        if self.caption:
            md += f'{self.caption.to_markdown()}\n'
        return md


class Image(FileObjectBlock[obj_blocks.Image], wraps=obj_blocks.Image):
    """Image block."""

    def to_markdown(self) -> str:
        alt = self.url.rsplit('/').pop()
        caption = self.caption.to_plain_text()
        if caption:
            return f'<figure><img src="{self.url}" alt="{alt}" /><figcaption>{caption}</figcaption></figure>\n'
        else:
            return f'![{alt}]({self.url})\n'


class Video(FileObjectBlock[obj_blocks.Video], wraps=obj_blocks.Video):
    """Video block."""

    def to_markdown(self) -> str:
        vtype = self.url.rsplit('.').pop()
        md = f'<video width="320" height="240" controls><source src="{self.url}" type="video/{vtype}"></video>\n'
        return md


class PDF(FileObjectBlock[obj_blocks.PDF], wraps=obj_blocks.PDF):
    """PDF block."""

    def to_markdown(self) -> str:
        name = self.url.rsplit('/').pop()
        md = f'[📖 {name}]({self.url})\n'
        if self.caption:
            md += f'{self.caption.to_markdown()}\n'
        return md


class ChildPage(Block[obj_blocks.ChildPage], wraps=obj_blocks.ChildPage):
    """Child page block."""

    def to_markdown(self) -> str:
        return f'[📄 **<u>{self.title}</u>**]({self.url})\n'

    @property
    def title(self) -> str:
        return self.obj_ref.child_page.title

    @property
    def url(self) -> str:
        return get_url(self.obj_ref.id)


class ChildDatabase(Block[obj_blocks.ChildDatabase], wraps=obj_blocks.ChildDatabase):
    """Child database block."""

    def to_markdown(self) -> str:
        return f'[**🗄️ {self.title}**]({self.url})\n'

    @property
    def title(self) -> str:
        return self.obj_ref.child_database.title

    @property
    def url(self) -> str:
        return get_url(self.obj_ref.id)


class Column(Block[obj_blocks.Column], ChildrenMixin, wraps=obj_blocks.Column):
    """Collumn block."""

    def to_markdown(self) -> str:
        mds = []
        for block in self.children:
            mds.append(block.to_markdown())
        return '\n'.join(mds)

    # @classmethod
    # def build(cls, *blocks):
    #     """Create a new `Column` block with the given blocks as children."""
    #     col = cls()

    #     for block in blocks:
    #         col.append(block)

    #     return col


class ColumnList(Block[obj_blocks.ColumnList], ChildrenMixin, wraps=obj_blocks.ColumnList):
    """Column list block."""

    def to_markdown(self) -> str:
        cols = []
        for i, block in enumerate(self.children):
            md = md_comment(f'column {i + 1}')
            cols.append(md + block.to_markdown())
        return '\n'.join(cols)

    # @classmethod
    # def build(cls, *columns):
    #     """Create a new `Column` block with the given blocks as children."""
    #     cols = cls()

    #     for col in columns:
    #         cols.append(col)

    #     return cols


class TableRow(Block[obj_blocks.TableRow], wraps=obj_blocks.TableRow):
    """Table row block."""

    @property
    def cells(self) -> list[RichText]:
        if self.obj_ref.table_row.cells is None:
            return []
        else:
            return [RichText.wrap_obj_ref(cell) for cell in self.obj_ref.table_row.cells]

    def to_markdown(self) -> str:
        return ' | '.join([cell.to_markdown() for cell in self.cells])

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


class Table(Block[obj_blocks.Table], ChildrenMixin, wraps=obj_blocks.Table):
    """Table block."""

    def __getitem__(self, index: tuple[int, int]) -> RichText:
        row_idx, col_idx = index
        return self.rows[row_idx].cells[col_idx]

    @property
    def width(self) -> int:
        return self.obj_ref.table.table_width

    @property
    def has_column_header(self) -> bool:
        return self.obj_ref.table.has_column_header

    @property
    def has_row_header(self) -> bool:
        return self.obj_ref.table.has_row_header

    @property
    def rows(self) -> list[TableRow]:
        return [cast(TableRow, row) for row in self.children]

    def to_markdown(self) -> str:
        headers = 'firstrow' if self.has_column_header else [''] * self.width
        table = [[cell.to_markdown() for cell in row.cells] for row in self.rows]
        return tabulate(table, headers, tablefmt='github') + '\n'

    # def build(cls, *rows):
    #     """Create a new `Table` block with the given rows."""
    #     table = cls()

    #     for row in rows:
    #         table.append(row)

    #     return table


class LinkToPage(Block[obj_blocks.LinkToPage], wraps=obj_blocks.LinkToPage):
    """Link to page block."""

    @property
    def url(self) -> str:
        return get_url(get_uuid(self.obj_ref.link_to_page))

    @property
    def page(self) -> Page:
        session = get_active_session()
        return session.get_page(get_uuid(self.obj_ref.link_to_page))

    def to_markdown(self) -> str:
        return f'[**↗️ <u>{self.page.title}</u>**]({self.url})\n'


class SyncedBlock(Block[obj_blocks.SyncedBlock], ChildrenMixin, wraps=obj_blocks.SyncedBlock):
    """Synced block - either original or synched."""

    @property
    def is_original(self) -> bool:
        """Is this block the original content."""
        return self.obj_ref.synced_block.synced_from is None

    @property
    def is_synched(self) -> bool:
        return not self.is_original

    @property
    def block(self) -> SyncedBlock:
        if self.is_original:
            return self
        elif (synched_from := self.obj_ref.synced_block.synced_from) is not None:
            session = get_active_session()
            return cast(SyncedBlock, session._get_block(get_uuid(synched_from)))
        else:
            msg = 'Unknown synched block, neither original nor synched!'
            raise RuntimeError(msg)

    def to_markdown(self, *, with_comment: bool = True) -> str:
        if self.is_original:
            md = md_comment('original block') if with_comment else ''
            md += '\n'.join([child.to_markdown() for child in self.children])
        else:
            md = md_comment('synched block') if with_comment else ''
            md += self.block.to_markdown(with_comment=False)
        return md


class Template(TextBlock[obj_blocks.Template], ChildrenMixin, wraps=obj_blocks.Template):
    """Template block."""

    def to_markdown(self) -> str:
        return f'<button type="button">{self.rich_text.to_markdown()}</button>\n'


class Unsupported(Block[obj_blocks.UnsupportedBlock], wraps=obj_blocks.UnsupportedBlock):
    """Unsupported blocks in the API."""

    def to_markdown(self) -> str:  # noqa: PLR6301
        return '<kbd>Unsupported block</kbd>\n'

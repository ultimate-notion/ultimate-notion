"""Core building blocks for pages and databases."""

from __future__ import annotations

import mimetypes
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeAlias, TypeGuard, TypeVar, cast
from uuid import UUID

from tabulate import tabulate
from typing_extensions import Self

from ultimate_notion.core import InvalidAPIUsageError, Wrapper, get_active_session, get_url
from ultimate_notion.file import Emoji, FileInfo, to_file_or_emoji, wrap_icon
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.enums import BGColor, CodeLang, Color
from ultimate_notion.text import RichText, RichTextBase, User, md_comment, text_to_obj_ref

if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.page import Page


T = TypeVar('T', bound=obj_blocks.DataObject)  # ToDo: Use new syntax when requires-python >= 3.12


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
        """Return the ID of the block."""
        return self.obj_ref.id

    @property
    def in_notion(self) -> bool:
        """Return whether the block was created in Notion."""
        return self.obj_ref.id is not None

    @property
    def created_time(self) -> datetime:
        """Return the time when the block was created."""
        return self.obj_ref.created_time

    @property
    def created_by(self) -> User:
        """Return the user who created the block."""
        session = get_active_session()
        return session.get_user(self.obj_ref.created_by.id)

    @property
    def last_edited_time(self) -> datetime:
        """Return the time when the block was last edited."""
        return self.obj_ref.last_edited_time

    @property
    def last_edited_by(self) -> User:
        """Return the user who last edited the block."""
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
            return session.get_block(block_ref=parent.block_id)
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
        """Return whether the object has children."""
        return self.obj_ref.has_children

    def _delete_me_from_parent(self) -> None:
        """Remove the block from the parent's children list."""
        if isinstance(self.parent, ChildrenMixin) and self.parent._children is not None:
            for idx, child in enumerate(self.parent.children):
                if child.id == self.id:
                    del self.parent._children[idx]
                    break

    def delete(self) -> Self:
        """Delete the block.

        Pages and databases are moved to the trash, blocks are deleted permanently.
        """
        session = get_active_session()
        self.obj_ref = cast(T, session.api.blocks.delete(self.id))
        self._delete_me_from_parent()
        return self

    @property
    def is_deleted(self) -> bool:
        """Return wether the object is in trash."""
        return self.obj_ref.in_trash or self.obj_ref.archived

    @property
    def is_page(self) -> bool:
        """Return whether the object is a page."""
        return False

    @property
    def is_db(self) -> bool:
        """Return whether the object is a database."""
        return False

    @abstractmethod
    def to_markdown(self) -> str:
        """Return the content of the block as Markdown."""
        ...


class ChildrenMixin(DataObject[T], wraps=obj_blocks.DataObject):
    """Mixin for data objects that can have children

    Note that we don't use the `children` property of some Notion objects, e.g. paragraph, quote, etc.,
    as not every object has this property, e.g. a page, database or toggable heading.
    """

    _children: list[Block] | None = None

    @property
    def children(self) -> list[Block]:
        """Return the children of this block."""
        if self._children is None:  # generate cache
            if self.is_deleted:
                msg = 'Cannot retrieve children of a deleted block from Notion.'
                raise RuntimeError(msg)
            else:
                session = get_active_session()
                child_blocks = session.api.blocks.children.list(parent=objs.get_uuid(self.obj_ref))
                self._children = [Block.wrap_obj_ref(block) for block in child_blocks]
        return self._children[:]  # we copy to allow block deletion while iterating over it

    def append(self, blocks: Block | list[Block], *, after: Block | None = None) -> Self:
        """Append a block or a list of blocks to the content of this block."""
        if not self.in_notion:
            msg = 'Cannot append blocks to a block that is not in Notion.'
            raise RuntimeError(msg)

        blocks = [blocks] if isinstance(blocks, Block) else blocks
        if not blocks:
            return self
        for block in blocks:
            if not isinstance(block, Block):
                msg = f'Cannot append {type(block)} to a block.'
                raise ValueError(msg)

        block_objs = [block.obj_ref for block in blocks]
        after_obj = None if after is None else after.obj_ref

        self._children = self.children  # force an initial load of the child blocks to append later
        session = get_active_session()
        block_objs, after_block_objs = session.api.blocks.children.append(self.obj_ref, block_objs, after=after_obj)
        blocks = [Block.wrap_obj_ref(block_obj) for block_obj in block_objs]

        if after is None:
            self._children.extend(blocks)
        else:
            insert_idx = next(idx for idx, block in enumerate(self._children) if block.id == after.id) + 1
            # we update the blocks after the position we want to insert.
            for block, updated_block_obj in zip(self._children[insert_idx:], after_block_objs, strict=True):
                block.obj_ref.update(**updated_block_obj.model_dump())
            self._children[insert_idx:insert_idx] = blocks

        self.obj_ref.has_children = True
        return self


BT = TypeVar('BT', bound=obj_blocks.Block)  # ToDo: Use new syntax when requires-python >= 3.12


class Block(DataObject[BT], ABC, wraps=obj_blocks.Block):
    """General Notion block."""

    @property
    def block_url(self) -> str:
        """Return the URL of the block."""
        return get_url(self.id)

    def reload(self) -> Self:
        """Reload the block from the API."""
        session = get_active_session()
        self.obj_ref = cast(BT, session.api.blocks.retrieve(self.id))
        return self


AnyBlock: TypeAlias = Block[Any]
"""For type hinting purposes, especially for lists of blocks, i.e. list[AnyBlock] in user code."""


class TextBlock(Block[BT], ABC, wraps=obj_blocks.TextBlock):
    """Abstract Text block."""

    def __init__(self, text: str | RichText | RichTextBase | list[RichTextBase]) -> None:
        super().__init__()
        self.obj_ref.value.rich_text = text_to_obj_ref(text)

    @property
    def rich_text(self) -> RichText:
        """Return the text content of this text block."""
        rich_texts = self.obj_ref.value.rich_text
        return RichText.wrap_obj_ref(rich_texts)


class Code(TextBlock[obj_blocks.Code], wraps=obj_blocks.Code):
    """Code block."""

    def __init__(
        self,
        text: str | RichText | RichTextBase | list[RichTextBase],
        *,
        language: CodeLang = CodeLang.PLAIN_TEXT,
        caption: str | RichText | RichTextBase | list[RichTextBase] | None = None,
    ) -> None:
        super().__init__(text)
        self.obj_ref.value.language = language
        self.obj_ref.value.caption = text_to_obj_ref(caption) if caption is not None else []

    @property
    def caption(self) -> RichText:
        return RichText.wrap_obj_ref(self.obj_ref.code.caption)

    def to_markdown(self) -> str:
        lang = self.obj_ref.code.language
        return f'```{lang}\n{self.rich_text.to_markdown()}\n```'


class ColoredTextBlock(TextBlock[BT], ABC, wraps=obj_blocks.TextBlock):
    """Abstract Text block with color."""

    def __init__(
        self,
        text: str | RichText | RichTextBase | list[RichTextBase],
        *,
        color: Color | BGColor = Color.DEFAULT,
    ) -> None:
        super().__init__(text)
        self.obj_ref.value.rich_text = text_to_obj_ref(text)
        self.obj_ref.value.color = color

    @property
    def color(self) -> Color | BGColor:
        return self.obj_ref.value.color


class Paragraph(ColoredTextBlock[obj_blocks.Paragraph], ChildrenMixin, wraps=obj_blocks.Paragraph):
    """Paragraph block."""

    def to_markdown(self) -> str:
        return f'{self.rich_text.to_markdown()}'


class Heading(ColoredTextBlock[BT], ChildrenMixin, ABC, wraps=obj_blocks.Heading):
    """Abstract Heading block."""

    def __init__(
        self,
        text: str | RichText | RichTextBase | list[RichTextBase],
        *,
        color: Color | BGColor = Color.DEFAULT,
        toggleable: bool = False,
    ) -> None:
        super().__init__(text, color=color)
        self.obj_ref.value.is_toggleable = toggleable

    @property
    def toggleable(self) -> bool:
        return self.obj_ref.value.is_toggleable

    def append(self, blocks: Block | list[Block], *, after: Block | None = None) -> Self:
        if not self.toggleable:
            msg = 'Cannot append blocks to a non-toggleable heading.'
            raise InvalidAPIUsageError(msg)
        return super().append(blocks, after=after)


class Heading1(Heading[obj_blocks.Heading1], wraps=obj_blocks.Heading1):
    """Heading 1 block."""

    def to_markdown(self) -> str:
        return f'## {self.rich_text.to_markdown()}'  # we use ## as # is used for page titles


class Heading2(Heading[obj_blocks.Heading2], wraps=obj_blocks.Heading2):
    """Heading 2 block."""

    def to_markdown(self) -> str:
        return f'### {self.rich_text.to_markdown()}'


class Heading3(Heading[obj_blocks.Heading3], wraps=obj_blocks.Heading3):
    """Heading 3 block."""

    def to_markdown(self) -> str:
        return f'#### {self.rich_text.to_markdown()}'


class Quote(ColoredTextBlock[obj_blocks.Quote], ChildrenMixin, wraps=obj_blocks.Quote):
    """Quote block."""

    def to_markdown(self) -> str:
        return f'> {self.rich_text.to_markdown()}\n'


class Callout(ColoredTextBlock[obj_blocks.Callout], wraps=obj_blocks.Callout):
    """Callout block."""

    def __init__(
        self,
        text: str | RichText | RichTextBase | list[RichTextBase],
        *,
        color: Color | BGColor = Color.DEFAULT,
        icon: FileInfo | Emoji | str | None = None,
    ) -> None:
        super().__init__(text, color=color)
        if icon is not None:
            self.obj_ref.value.icon = to_file_or_emoji(icon).obj_ref

    @property
    def icon(self) -> FileInfo | Emoji | None:
        return wrap_icon(self.obj_ref.callout.icon)

    def to_markdown(self) -> str:
        if isinstance(icon := self.icon, Emoji):
            return f'{icon} {self.rich_text.to_markdown()}\n'
        elif isinstance(icon := self.icon, FileInfo):
            return f'![icon]({icon.url}) {self.rich_text.to_markdown()}\n'
        else:
            return f'{self.rich_text.to_markdown()}\n'


class BulletedItem(ColoredTextBlock[obj_blocks.BulletedListItem], ChildrenMixin, wraps=obj_blocks.BulletedListItem):
    """Bulleted list item."""

    def to_markdown(self) -> str:
        return f'- {self.rich_text.to_markdown()}\n'


class NumberedItem(ColoredTextBlock[obj_blocks.NumberedListItem], ChildrenMixin, wraps=obj_blocks.NumberedListItem):
    """Numbered list item."""

    def to_markdown(self) -> str:
        return f'1. {self.rich_text.to_markdown()}\n'


class ToDoItem(ColoredTextBlock[obj_blocks.ToDo], ChildrenMixin, wraps=obj_blocks.ToDo):
    """ToDo list item."""

    def __init__(
        self,
        text: str | RichText | RichTextBase | list[RichTextBase],
        *,
        checked: bool = False,
        color: Color | BGColor = Color.DEFAULT,
    ) -> None:
        super().__init__(text, color=color)
        self.obj_ref.value.checked = checked

    def is_checked(self) -> bool:
        return self.obj_ref.to_do.checked

    def to_markdown(self) -> str:
        mark = 'x' if self.is_checked() else ' '
        return f'- [{mark}] {self.rich_text.to_markdown()}\n'


class ToggleItem(ColoredTextBlock[obj_blocks.Toggle], ChildrenMixin, wraps=obj_blocks.Toggle):
    """Toggle list item."""

    def to_markdown(self) -> str:
        return f'- {self.rich_text.to_markdown()}\n'


class Divider(Block[obj_blocks.Divider], wraps=obj_blocks.Divider):
    """Divider block."""

    def to_markdown(self) -> str:  # noqa: PLR6301
        return '---\n'


class TableOfContents(Block[obj_blocks.TableOfContents], wraps=obj_blocks.TableOfContents):
    """Table of contents block."""

    def __init__(self, *, color: Color | BGColor = Color.DEFAULT):
        super().__init__()
        self.obj_ref.value.color = color

    def to_markdown(self) -> str:  # noqa: PLR6301
        return '```{toc}\n```'


class Breadcrumb(Block[obj_blocks.Breadcrumb], wraps=obj_blocks.Breadcrumb):
    """Breadcrumb block."""

    def to_markdown(self) -> str:
        def is_page(obj: DataObject) -> TypeGuard[Page]:
            return obj.is_page

        return ' / '.join(ancestor.title for ancestor in self.ancestors if is_page(ancestor)) + '\n'


class Embed(Block[obj_blocks.Embed], wraps=obj_blocks.Embed):
    """Embed block."""

    def __init__(self, url: str, *, caption: str | RichText | RichTextBase | list[RichTextBase] | None = None):
        super().__init__()
        self.obj_ref.value.url = url
        self.obj_ref.value.caption = text_to_obj_ref(caption) if caption is not None else None

    @property
    def url(self) -> str | None:
        """Return the URL of the embedded item."""
        return self.obj_ref.embed.url

    @property
    def caption(self) -> RichText:
        return RichText.wrap_obj_ref(self.obj_ref.embed.caption)

    def to_markdown(self) -> str:
        if self.url is not None:
            return f'[{self.url}]({self.url})\n'
        else:
            return ''


class Bookmark(Block[obj_blocks.Bookmark], wraps=obj_blocks.Bookmark):
    """Bookmark block."""

    def __init__(self, url: str, *, caption: str | RichText | RichTextBase | list[RichTextBase] | None = None):
        super().__init__()
        self.obj_ref.value.url = url
        self.obj_ref.value.caption = text_to_obj_ref(caption) if caption is not None else None

    @property
    def url(self) -> str | None:
        """Return the URL of the bookmark."""
        return self.obj_ref.bookmark.url

    def to_markdown(self) -> str:
        if self.url is not None:
            return f'Bookmark: [{self.url}]({self.url})\n'
        else:
            return 'Bookmark: [Add a web bookmark]()\n'  # emtpy bookmark


class LinkPreview(Block[obj_blocks.LinkPreview], wraps=obj_blocks.LinkPreview):
    """Link preview block.

    !!! warning "Not Supported"

        The `link_preview` block can only be returned as part of a response.
        The Notion API does not support creating or appending `link_preview` blocks.
    """

    def __init__(self, url: str):
        msg = 'The Notion API does not support creating or appending `link_preview` blocks.'
        raise NotImplementedError(msg)
        # ToDo: Implement this when the API supports it
        # super().__init__()
        # self.obj_ref.value.url = url

    @property
    def url(self) -> str | None:
        return self.obj_ref.link_preview.url

    def to_markdown(self) -> str:
        if self.block_url is not None:
            return f'Link preview: [{self.url}]({self.url})\n'
        return super().to_markdown()


class Equation(Block[obj_blocks.Equation], wraps=obj_blocks.Equation):
    """Equation block.

    LaTeX equation in display mode, e.g. `$$ \\mathrm{E=mc^2} $$`, but without the `$$` signs.
    """

    def __init__(self, expression: str):
        super().__init__()
        self.obj_ref.value.expression = expression

    @property
    def expression(self) -> str:
        if (expr := self.obj_ref.equation.expression) is not None:
            return expr.rstrip()
        else:
            return ''

    def to_markdown(self) -> str:
        return f'$$\n{self.expression}\n$$\n'


FT = TypeVar('FT', bound=obj_blocks.FileBase)


class FileBaseBlock(Block[FT], ABC, wraps=obj_blocks.FileBase):
    """Abstract Block for file-based blocks."""

    def __init__(
        self,
        url: str,
        *,
        caption: str | RichText | RichTextBase | list[RichTextBase] | None = None,
    ):
        super().__init__()
        caption_obj = text_to_obj_ref(caption) if caption is not None else None
        external_file = objs.ExternalFile.build(url=url, caption=caption_obj)
        setattr(self.obj_ref, self.obj_ref.type, external_file)

    @property
    def file(self) -> FileInfo:
        if isinstance(file_obj := self.obj_ref.value, objs.FileObject):
            return FileInfo.wrap_obj_ref(file_obj)
        else:
            msg = f'Unknown file type {type(file_obj)}'
            raise ValueError(msg)

    @property
    def url(self) -> str:
        return self.file.url

    @property
    def caption(self) -> RichText:
        return self.file.caption


class File(FileBaseBlock[obj_blocks.File], wraps=obj_blocks.File):
    """File block."""

    def __init__(
        self,
        name: str,
        url: str,
        *,
        caption: str | RichText | RichTextBase | list[RichTextBase] | None = None,
    ):
        super().__init__(url, caption=caption)
        self.obj_ref.value.name = name

    @property
    def name(self) -> str:
        name = self.file.name
        return name if name is not None else ''

    def to_markdown(self) -> str:
        md = f'[📎 {self.name}]({self.url})\n'
        if self.caption:
            md += f'{self.caption.to_markdown()}\n'
        return md


class Image(FileBaseBlock[obj_blocks.Image], wraps=obj_blocks.Image):
    """Image block."""

    def __init__(self, url: str, *, caption: str | RichText | RichTextBase | list[RichTextBase] | None = None):
        super().__init__(url, caption=caption)

    def to_markdown(self) -> str:
        alt = self.url.rsplit('/').pop()
        caption = self.caption.to_plain_text()
        if caption:
            return f'<figure><img src="{self.url}" alt="{alt}" /><figcaption>{caption}</figcaption></figure>\n'
        else:
            return f'![{alt}]({self.url})\n'


class Video(FileBaseBlock[obj_blocks.Video], wraps=obj_blocks.Video):
    """Video block."""

    def to_markdown(self) -> str:
        mime_type, _ = mimetypes.guess_type(self.url)
        vtype = f' type="{mime_type}"' if mime_type else ''
        md = f'<video width="320" height="240" controls><source src="{self.url}"{vtype}></video>\n'
        return md


class PDF(FileBaseBlock[obj_blocks.PDF], wraps=obj_blocks.PDF):
    """PDF block."""

    def to_markdown(self) -> str:
        name = self.url.rsplit('/').pop()
        md = f'[📖 {name}]({self.url})\n'
        if self.caption:
            md += f'{self.caption.to_markdown()}\n'
        return md


class ChildPage(Block[obj_blocks.ChildPage], wraps=obj_blocks.ChildPage):
    """Child page block.

    !!! note

        To create a child page block, create a new page with the corresponding parent.
    """

    def __init__(self):
        msg = 'To create a child page block, create a new page with the corresponding parent.'
        raise InvalidAPIUsageError(msg)

    def to_markdown(self) -> str:
        """Return the reference to this page as Markdown."""
        return f'[📄 **<u>{self.title}</u>**]({self.block_url})\n'

    @property
    def title(self) -> str:
        """Return the title of the child page."""
        return self.obj_ref.child_page.title

    @property
    def page(self) -> Page:
        """Return the actual Page object."""
        sess = get_active_session()
        return sess.get_page(self.obj_ref.id)


class ChildDatabase(Block[obj_blocks.ChildDatabase], wraps=obj_blocks.ChildDatabase):
    """Child database block.

    !!! note

        To create a child database block as an end-user, create a new database with the corresponding parent.
    """

    def __init__(self):
        msg = 'To create a child database block, create a new database with the corresponding parent.'
        raise InvalidAPIUsageError(msg)

    def to_markdown(self) -> str:
        """Return the reference to this database as Markdown."""
        return f'[**🗄️ {self.title}**]({self.block_url})\n'

    @property
    def title(self) -> str:
        """Return the title of the child database"""
        return self.obj_ref.child_database.title

    @property
    def db(self) -> Database:
        """Return the actual Database object."""
        sess = get_active_session()
        return sess.get_db(self.obj_ref.id)


class Column(Block[obj_blocks.Column], ChildrenMixin, wraps=obj_blocks.Column):
    """Column block."""

    def __init__(self):
        msg = 'Column blocks cannot be created directly. Use `Columns` instead.'
        raise InvalidAPIUsageError(msg)

    def to_markdown(self) -> str:
        mds = []
        for block in self.children:
            mds.append(block.to_markdown())
        return '\n'.join(mds)


class Columns(Block[obj_blocks.ColumnList], ChildrenMixin, wraps=obj_blocks.ColumnList):
    """Columns block."""

    def __init__(self, n_columns: int):
        """Create a new `Columns` block with the given number of columns."""
        super().__init__()
        self.obj_ref.column_list.children = [obj_blocks.Column.build() for _ in range(n_columns)]

    def __getitem__(self, index: int) -> Column:
        return cast(Column, self.children[index])

    def to_markdown(self) -> str:
        cols = []
        for i, block in enumerate(self.children):
            md = md_comment(f'column {i + 1}')
            cols.append(md + block.to_markdown())
        return '\n'.join(cols)


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


class Table(Block[obj_blocks.Table], ChildrenMixin, wraps=obj_blocks.Table):
    """Table block."""

    def __init__(self, n_rows: int, n_cols: int, *, column_header: bool = False, row_header: bool = False):
        super().__init__()
        self.obj_ref.table.table_width = n_cols
        self.obj_ref.table.has_column_header = column_header
        self.obj_ref.table.has_row_header = row_header
        self.obj_ref.table.children = [obj_blocks.TableRow.build(n_cols) for _ in range(n_rows)]

    def __getitem__(self, index: tuple[int, int]) -> RichText:
        row_idx, col_idx = index
        return self.rows[row_idx].cells[col_idx]

    @property
    def width(self) -> int:
        """Return the width, i.e. number of columns, of the table."""
        return self.obj_ref.table.table_width

    @property
    def shape(self) -> tuple[int, int]:
        """Return the shape of the table."""
        n_cols = self.width
        n_rows = len(self.children)
        return n_rows, n_cols

    @property
    def has_column_header(self) -> bool:
        """Return whether the table has a column header."""
        return self.obj_ref.table.has_column_header

    @property
    def has_row_header(self) -> bool:
        """Return whether the table has a row header."""
        return self.obj_ref.table.has_row_header

    @property
    def rows(self) -> list[TableRow]:
        """Return the rows of the table."""
        return [cast(TableRow, row) for row in self.children]

    def to_markdown(self) -> str:
        """Return the table as Markdown."""
        headers = 'firstrow' if self.has_column_header else [''] * self.width
        table = [[cell.to_markdown() for cell in row.cells] for row in self.rows]
        return tabulate(table, headers, tablefmt='github') + '\n'


class LinkToPage(Block[obj_blocks.LinkToPage], wraps=obj_blocks.LinkToPage):
    """Link to page block."""

    def __init__(self, page: Page):
        super().__init__()
        self.obj_ref.link_to_page = objs.PageRef.build(page.obj_ref)

    @property
    def url(self) -> str:
        return get_url(objs.get_uuid(self.obj_ref.link_to_page))

    @property
    def page(self) -> Page:
        session = get_active_session()
        return session.get_page(objs.get_uuid(self.obj_ref.link_to_page))

    def to_markdown(self) -> str:
        return f'[**↗️ <u>{self.page.title}</u>**]({self.url})\n'


class SyncedBlock(Block[obj_blocks.SyncedBlock], ChildrenMixin, wraps=obj_blocks.SyncedBlock):
    """Synced block - either original or synced."""

    def __init__(self, blocks: Block | list[Block]):
        """Create the original synced block."""
        super().__init__()
        blocks = [blocks] if isinstance(blocks, Block) else blocks
        self.obj_ref.synced_block.children = [block.obj_ref for block in blocks]

    @property
    def is_original(self) -> bool:
        """Return if this block is the original block."""
        return self.obj_ref.synced_block.synced_from is None

    @property
    def is_synced(self) -> bool:
        """Return if this block is synced from another block."""
        return not self.is_original

    def get_original(self) -> SyncedBlock:
        """Return the original block."""
        if self.is_original:
            return self
        elif (synced_from := self.obj_ref.synced_block.synced_from) is not None:
            session = get_active_session()
            return cast(SyncedBlock, session.get_block(objs.get_uuid(synced_from)))
        else:
            msg = 'Unknown synced block, neither original nor synced!'
            raise RuntimeError(msg)

    def create_synced(self) -> SyncedBlock:
        """Return the synced block for appending."""
        if not self.in_notion:
            msg = 'Cannot create a synced block for a block that is not in Notion. Append first!'
            raise RuntimeError(msg)

        if not self.is_original:
            msg = 'Cannot create a synced block for a block that is already synced.'
            raise RuntimeError(msg)

        obj = obj_blocks.SyncedBlock.build()
        obj.synced_block.synced_from = obj_blocks.BlockRef.build(self.obj_ref)
        return self.wrap_obj_ref(obj)

    def to_markdown(self, *, with_comment: bool = True) -> str:
        if self.is_original:
            md = md_comment('original block') if with_comment else ''
            md += '\n'.join([child.to_markdown() for child in self.children])
        else:
            md = md_comment('synced block') if with_comment else ''
            md += self.get_original().to_markdown(with_comment=False)
        return md


class Template(TextBlock[obj_blocks.Template], ChildrenMixin, wraps=obj_blocks.Template):
    """Template block.

    !!! warning "Deprecated"

        As of March 27, 2023 creation of template blocks will no longer be supported.
    """

    def __init__(self):
        msg = 'A template block cannot be created by a user.'
        raise InvalidAPIUsageError(msg)

    def to_markdown(self) -> str:
        return f'<button type="button">{self.rich_text.to_markdown()}</button>\n'


class Unsupported(Block[obj_blocks.UnsupportedBlock], wraps=obj_blocks.UnsupportedBlock):
    """Unsupported block in the API."""

    def __init__(self):
        msg = 'An unsupported block cannot be created by a user.'
        raise InvalidAPIUsageError(msg)

    def to_markdown(self) -> str:  # noqa: PLR6301
        return '<kbd>Unsupported block</kbd>\n'

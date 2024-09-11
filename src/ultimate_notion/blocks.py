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
from ultimate_notion.file import Emoji, FileInfo, wrap_icon
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
    def block_url(self) -> str:
        """Return the URL of the block.

        !!! note

            Databases and pages are also considered blocks in Notion but they also have a
            long-form URL. Use the `url` property to get the long-form URL.
        """
        return get_url(self.id)

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
            for idx, child in enumerate(self.parent._children):
                if child.id == self.id:
                    del self.parent._children[idx]
                    break
            self.parent.obj_ref.has_children = bool(self.parent._children)

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

    def _to_markdown(self) -> str:
        """Return the content of the block as Markdown.

        This method can be overridden to provide a custom Markdown representation,
        e.g. for a page/database child block.
        """
        return self.to_markdown()


class ChildrenMixin(DataObject[T], wraps=obj_blocks.DataObject):
    """Mixin for data objects that can have children

    Note that we don't use the `children` property of some Notion objects, e.g. paragraph, quote, etc.,
    as not every object has this property, e.g. a page, database or toggable heading.
    """

    _children: list[Block] | None = None

    def _gen_children_cache(self) -> list[Block]:
        """Generate the children cache."""
        if self.is_deleted:
            msg = 'Cannot retrieve children of a deleted block from Notion.'
            raise RuntimeError(msg)

        session = get_active_session()
        child_blocks_objs = session.api.blocks.children.list(parent=objs.get_uuid(self.obj_ref))
        child_blocks = [Block.wrap_obj_ref(block) for block in child_blocks_objs]

        for idx, child_block in enumerate(child_blocks):
            if isinstance(child_block, ChildPage):
                child_blocks[idx] = cast(Block, child_block.page)
            elif isinstance(child_block, ChildDatabase):
                child_blocks[idx] = cast(Block, child_block.db)

        return [cast(Block, session.cache.setdefault(block.id, block)) for block in child_blocks]

    @property
    def children(self) -> list[Block]:
        """Return the children of this block."""
        if self._children is None:
            self._children = self._gen_children_cache()
            self.obj_ref.has_children = bool(self._children)  # update the property manually to avoid API call
        return self._children[:]  # we copy to allow deleting blocks while iterating over it

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
            if block.in_notion:
                msg = 'Cannot append a block that is already in Notion.'
                raise InvalidAPIUsageError(msg)

        if self._children is None:
            self._children = self._gen_children_cache()

        session = get_active_session()
        block_objs = [block.obj_ref for block in blocks]
        after_obj = None if after is None else after.obj_ref
        block_objs, after_block_objs = session.api.blocks.children.append(self.obj_ref, block_objs, after=after_obj)

        for block, obj in zip(blocks, block_objs, strict=True):
            block.obj_ref = obj
            session.cache[block.id] = block

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

    def reload(self) -> Self:
        """Reload the block from the API."""
        session = get_active_session()
        self.obj_ref = cast(BT, session.api.blocks.retrieve(self.id))
        return self

    def _update_in_notion(self) -> None:
        """Update the locally modified block on Notion."""
        if self.in_notion:
            session = get_active_session()
            self.obj_ref = cast(BT, session.api.blocks.update(self.obj_ref))


AnyBlock: TypeAlias = Block[Any]
"""For type hinting purposes, especially for lists of blocks, i.e. list[AnyBlock], in user code."""


class TextBlock(Block[BT], ABC, wraps=obj_blocks.TextBlock):
    """Abstract Text block."""

    def __init__(self, text: str | RichText | RichTextBase) -> None:
        super().__init__()
        self.obj_ref.value.rich_text = text_to_obj_ref(text)

    @property
    def rich_text(self) -> RichText:
        """Return the text content of this text block."""
        rich_texts = self.obj_ref.value.rich_text
        return RichText.wrap_obj_ref(rich_texts)

    @rich_text.setter
    def rich_text(self, text: str | RichText | RichTextBase) -> None:
        # Right now this leads to a mypy error, see
        # https://github.com/python/mypy/issues/3004
        # Always pass `RichText` objects to this setter to avoid this error.
        self.obj_ref.value.rich_text = text_to_obj_ref(text)
        self._update_in_notion()


class Code(TextBlock[obj_blocks.Code], wraps=obj_blocks.Code):
    """Code block."""

    def __init__(
        self,
        text: str | RichText | RichTextBase,
        *,
        language: CodeLang = CodeLang.PLAIN_TEXT,
        caption: str | RichText | RichTextBase | None = None,
    ) -> None:
        super().__init__(text)
        self.obj_ref.value.language = language
        self.obj_ref.value.caption = text_to_obj_ref(caption) if caption is not None else []

    @property
    def language(self) -> CodeLang:
        return self.obj_ref.value.language

    @language.setter
    def language(self, language: CodeLang) -> None:
        self.obj_ref.value.language = language
        self._update_in_notion()

    @property
    def caption(self) -> RichText:
        return RichText.wrap_obj_ref(self.obj_ref.value.caption)

    @caption.setter
    def caption(self, caption: str | RichText | RichTextBase | None) -> None:
        self.obj_ref.value.caption = text_to_obj_ref(caption) if caption is not None else []
        self._update_in_notion()

    def to_markdown(self) -> str:
        lang = self.obj_ref.value.language
        return f'```{lang}\n{self.rich_text.to_markdown()}\n```'


class ColoredTextBlock(TextBlock[BT], ABC, wraps=obj_blocks.TextBlock):
    """Abstract Text block with color."""

    def __init__(
        self,
        text: str | RichText | RichTextBase,
        *,
        color: Color | BGColor = Color.DEFAULT,
    ) -> None:
        super().__init__(text)
        self.obj_ref.value.rich_text = text_to_obj_ref(text)
        self.obj_ref.value.color = color

    @property
    def color(self) -> Color | BGColor:
        return self.obj_ref.value.color

    @color.setter
    def color(self, color: Color | BGColor) -> None:
        self.obj_ref.value.color = color
        self._update_in_notion()


class Paragraph(ColoredTextBlock[obj_blocks.Paragraph], ChildrenMixin, wraps=obj_blocks.Paragraph):
    """Paragraph block."""

    def to_markdown(self) -> str:
        return f'{self.rich_text.to_markdown()}'


class Heading(ColoredTextBlock[BT], ChildrenMixin, ABC, wraps=obj_blocks.Heading):
    """Abstract Heading block."""

    def __init__(
        self,
        text: str | RichText | RichTextBase,
        *,
        color: Color | BGColor = Color.DEFAULT,
        toggleable: bool = False,
    ) -> None:
        super().__init__(text, color=color)
        self.obj_ref.value.is_toggleable = toggleable

    @property
    def toggleable(self) -> bool:
        """Return whether the heading is toggleable."""
        return self.obj_ref.value.is_toggleable

    @toggleable.setter
    def toggleable(self, toggleable: bool) -> None:
        """Set the heading to be toggleable or not."""
        if self.toggleable and self.has_children:
            msg = 'Cannot make a toggleable heading non-toggleable if it has children.'
            raise InvalidAPIUsageError(msg)
        self.obj_ref.value.is_toggleable = toggleable
        self._update_in_notion()

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


class Callout(ColoredTextBlock[obj_blocks.Callout], ChildrenMixin, wraps=obj_blocks.Callout):
    """Callout block.

    !!! note

        The default icon is an electric light bulb, i.e. 💡 in case `None` is passed as icon.
        It is not possible to remove the icon, but you can change it to a different emoji or a file.
    """

    def __init__(
        self,
        text: str | RichText | RichTextBase,
        *,
        color: Color | BGColor = Color.DEFAULT,
        icon: FileInfo | Emoji | None = None,
    ) -> None:
        super().__init__(text, color=color)
        if icon is not None:
            self.obj_ref.value.icon = icon.obj_ref

    @staticmethod
    def get_default_icon() -> Emoji:
        """Return the default icon of a callout block."""
        return Emoji('💡')

    @property
    def icon(self) -> FileInfo | Emoji:
        if (icon := self.obj_ref.value.icon) is None:
            return self.get_default_icon()
        else:
            return wrap_icon(icon)

    @icon.setter
    def icon(self, icon: FileInfo | Emoji | None) -> None:
        if icon is None:
            icon = self.get_default_icon()
        self.obj_ref.value.icon = icon.obj_ref
        self._update_in_notion()

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
        text: str | RichText | RichTextBase,
        *,
        checked: bool = False,
        color: Color | BGColor = Color.DEFAULT,
    ) -> None:
        super().__init__(text, color=color)
        self.obj_ref.value.checked = checked

    @property
    def checked(self) -> bool:
        return self.obj_ref.to_do.checked

    @checked.setter
    def checked(self, checked: bool) -> None:
        self.obj_ref.value.checked = checked
        self._update_in_notion()

    def to_markdown(self) -> str:
        mark = 'x' if self.checked else ' '
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

    def __init__(self, url: str, *, caption: str | RichText | RichTextBase | None = None):
        super().__init__()
        self.obj_ref.value.url = url
        self.obj_ref.value.caption = text_to_obj_ref(caption) if caption is not None else None

    @property
    def url(self) -> str | None:
        """Return the URL of the embedded item."""
        return self.obj_ref.value.url

    @url.setter
    def url(self, url: str) -> None:
        self.obj_ref.value.url = url
        self._update_in_notion()

    @property
    def caption(self) -> RichText:
        """Return the caption of the embedded item."""
        return RichText.wrap_obj_ref(self.obj_ref.value.caption)

    @caption.setter
    def caption(self, caption: str | RichText | RichTextBase | None) -> None:
        self.obj_ref.value.caption = text_to_obj_ref(caption) if caption is not None else []
        self._update_in_notion()

    def to_markdown(self) -> str:
        if self.url is not None:
            return f'[{self.url}]({self.url})\n'
        else:
            return ''


class Bookmark(Block[obj_blocks.Bookmark], wraps=obj_blocks.Bookmark):
    """Bookmark block."""

    def __init__(self, url: str, *, caption: str | RichText | RichTextBase | None = None):
        super().__init__()
        self.obj_ref.value.url = url
        self.obj_ref.value.caption = text_to_obj_ref(caption) if caption is not None else None

    @property
    def url(self) -> str | None:
        """Return the URL of the bookmark."""
        return self.obj_ref.value.url

    @url.setter
    def url(self, url: str) -> None:
        self.obj_ref.value.url = url
        self._update_in_notion()

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
        return self.obj_ref.value.url

    def to_markdown(self) -> str:
        if self.block_url is not None:
            return f'Link preview: [{self.url}]({self.url})\n'
        return super().to_markdown()


class Equation(Block[obj_blocks.Equation], wraps=obj_blocks.Equation):
    """Equation block.

    LaTeX equation in display mode, e.g. `$$ \\mathrm{E=mc^2} $$`, but without the `$$` signs.
    """

    def __init__(self, latex: str):
        super().__init__()
        self.obj_ref.value.expression = latex

    @property
    def latex(self) -> str:
        if (expr := self.obj_ref.equation.expression) is not None:
            return expr.rstrip()
        else:
            return ''

    @latex.setter
    def latex(self, latex: str) -> None:
        self.obj_ref.value.expression = latex
        self._update_in_notion()

    def to_markdown(self) -> str:
        return f'$$\n{self.latex}\n$$\n'


FT = TypeVar('FT', bound=obj_blocks.FileBase)


class FileBaseBlock(Block[FT], ABC, wraps=obj_blocks.FileBase):
    """Abstract Block for file-based blocks."""

    def __init__(
        self,
        url: str,
        *,
        caption: str | RichText | RichTextBase | None = None,
        name: str | None = None,
    ):
        super().__init__()
        file_info = FileInfo(url=url, name=name, caption=caption)
        self.obj_ref.value = file_info.obj_ref

    @property
    def file_info(self) -> FileInfo:
        """Return the file information of this block as a copy."""
        if isinstance(file_obj := self.obj_ref.value, objs.FileObject):
            return FileInfo.wrap_obj_ref(file_obj.model_copy(deep=True))
        else:
            msg = f'Unknown file type {type(file_obj)}'
            raise ValueError(msg)

    @property
    def url(self) -> str:
        return self.file_info.url

    @property
    def caption(self) -> RichText:
        return self.file_info.caption

    @caption.setter
    def caption(self, caption: str | RichText | RichTextBase | None) -> None:
        self.obj_ref.value.caption = text_to_obj_ref(caption) if caption is not None else []
        self._update_in_notion()


class File(FileBaseBlock[obj_blocks.File], wraps=obj_blocks.File):
    """File block.

    !!! note

        Only the caption and name can be modified, the URL is read-only.
        Note that only the file name not the file suffix can be modified,
        the suffix is determined initially by the url.
    """

    def __init__(
        self,
        name: str,
        url: str,
        *,
        caption: str | RichText | RichTextBase | None = None,
    ):
        super().__init__(url, caption=caption, name=name)

    @property
    def name(self) -> str:
        name = self.file_info.name
        return name if name is not None else ''

    @name.setter
    def name(self, name: str) -> None:
        self.obj_ref.value.name = name
        self._update_in_notion()

    def to_markdown(self) -> str:
        md = f'[📎 {self.name}]({self.url})\n'
        if self.caption:
            md += f'{self.caption.to_markdown()}\n'
        return md


class Image(FileBaseBlock[obj_blocks.Image], wraps=obj_blocks.Image):
    """Image block.

    !!! note

        Only the caption can be modified, the URL is read-only.
    """

    def __init__(self, url: str, *, caption: str | RichText | RichTextBase | None = None):
        super().__init__(url, caption=caption)

    def to_markdown(self) -> str:
        alt = self.url.rsplit('/').pop()
        caption = self.caption.to_plain_text()
        if caption:
            return f'<figure><img src="{self.url}" alt="{alt}" /><figcaption>{caption}</figcaption></figure>\n'
        else:
            return f'![{alt}]({self.url})\n'


class Video(FileBaseBlock[obj_blocks.Video], wraps=obj_blocks.Video):
    """Video block.

    !!! note

        Only the caption can be modified, the URL is read-only.
    """

    def to_markdown(self) -> str:
        mime_type, _ = mimetypes.guess_type(self.url)
        vtype = f' type="{mime_type}"' if mime_type else ''
        md = f'<video width="320" height="240" controls><source src="{self.url}"{vtype}></video>\n'
        return md


class PDF(FileBaseBlock[obj_blocks.PDF], wraps=obj_blocks.PDF):
    """PDF block.

    !!! note

        Only the caption can be modified, the URL is read-only.
    """

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
        This block is used only internally.
    """

    def __init__(self):
        msg = 'To create a child page block, create a new page with the corresponding parent.'
        raise InvalidAPIUsageError(msg)

    @property
    def title(self) -> str:
        """Return the title of the child page."""
        return self.obj_ref.child_page.title

    @property
    def page(self) -> Page:
        """Return the actual Page object."""
        sess = get_active_session()
        return sess.get_page(self.obj_ref.id)

    def to_markdown(self) -> str:  # noqa: PLR6301
        msg = '`ChildPage` is only used internally, work with a proper `Page` instead.'
        raise InvalidAPIUsageError(msg)


class ChildDatabase(Block[obj_blocks.ChildDatabase], wraps=obj_blocks.ChildDatabase):
    """Child database block.

    !!! note

        To create a child database block as an end-user, create a new database with the corresponding parent.
        This block is used only internally.
    """

    def __init__(self):
        msg = 'To create a child database block, create a new database with the corresponding parent.'
        raise InvalidAPIUsageError(msg)

    @property
    def title(self) -> str:
        """Return the title of the child database"""
        return self.obj_ref.child_database.title

    @property
    def db(self) -> Database:
        """Return the actual Database object."""
        sess = get_active_session()
        return sess.get_db(self.obj_ref.id)

    def to_markdown(self) -> str:  # noqa: PLR6301
        msg = '`ChildDatabase` is only used internally, work with a proper `Database` instead.'
        raise InvalidAPIUsageError(msg)


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

    def add_column(self, index: int = -1) -> Self:
        """Add a new column to the columns block."""
        if 1 <= index <= len(self.children):
            new_col = Column.wrap_obj_ref(obj_blocks.Column.build())
            self.append(new_col, after=self.children[index - 1])
            return self
        else:
            msg = f'Columns can only be inserted from index 1 to {len(self.children)}.'
            raise ValueError(msg)

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

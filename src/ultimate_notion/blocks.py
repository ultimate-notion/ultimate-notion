"""Blocks that make up the content of a page."""

from __future__ import annotations

import itertools
import mimetypes
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, TypeAlias, TypeGuard, TypeVar, cast, overload

from tabulate import tabulate
from typing_extensions import Self

from ultimate_notion.comment import Comment, Discussion
from ultimate_notion.core import InvalidAPIUsageError, NotionEntity, get_active_session, get_url
from ultimate_notion.file import Emoji, FileInfo, wrap_icon
from ultimate_notion.markdown import md_comment
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.enums import BGColor, CodeLang, Color
from ultimate_notion.rich_text import Text, User
from ultimate_notion.utils import del_nested_attr

if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.page import Page


DO = TypeVar('DO', bound=obj_blocks.DataObject)  # ToDo: Use new syntax when requires-python >= 3.12


class DataObject(NotionEntity[DO], wraps=obj_blocks.DataObject):
    """The base type for all data-related types, i.e, pages, databases and blocks."""

    @property
    def block_url(self) -> str:
        """Return the URL of the block.

        !!! note

            Databases and pages are also considered blocks in Notion but they also have a
            long-form URL. Use the `url` property to get the long-form URL.
        """
        return get_url(self.id)

    @property
    def last_edited_by(self) -> User:
        """Return the user who last edited the block."""
        session = get_active_session()
        return session.get_user(self.obj_ref.last_edited_by.id)

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
        self.obj_ref = cast(DO, session.api.blocks.delete(self.id))
        self._delete_me_from_parent()
        return self

    @property
    def is_deleted(self) -> bool:
        """Return wether the object is in trash."""
        return self.obj_ref.in_trash or self.obj_ref.archived

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


class ChildrenMixin(DataObject[DO], wraps=obj_blocks.DataObject):
    """Mixin for data objects that can have children

    Note that we don't use the `children` property of some Notion objects, e.g. paragraph, quote, etc.,
    as not every object has this property, e.g. a page, database or toggable heading.
    """

    # ToDo: This could be reworked to differentiate between blocks that have a children attribute and those that don't,
    # like headings and pages. In the former case we would not neet to have a _children attribute and could directly
    # access the children attribute of the object reference. In the latter case we would need to have a _children.
    # This would save some memory and appending would work for the former case even for blocks that are not
    # yet in Notion.

    _children: list[Block] | None = None

    def _gen_children_cache(self) -> list[Block]:
        """Generate the children cache."""
        if self.is_deleted:
            msg = 'Cannot retrieve children of a deleted block from Notion.'
            raise RuntimeError(msg)

        session = get_active_session()
        child_blocks_objs = list(session.api.blocks.children.list(parent=objs.get_uuid(self.obj_ref)))
        self.obj_ref.has_children = bool(child_blocks_objs)  # update the property manually to avoid API call
        if isinstance(self.obj_ref, obj_blocks.Block) and hasattr(self.obj_ref.value, 'children'):
            self.obj_ref.value.children = child_blocks_objs  # update the children attribute

        child_blocks: list[Block] = [Block.wrap_obj_ref(block) for block in child_blocks_objs]

        for idx, child_block in enumerate(child_blocks):
            if isinstance(child_block, ChildPage):
                child_blocks[idx] = cast(Block, child_block.page)
            elif isinstance(child_block, ChildDatabase):
                child_blocks[idx] = cast(Block, child_block.db)

        return [cast(Block, session.cache.setdefault(block.id, block)) for block in child_blocks]

    @property
    def children(self) -> tuple[Block, ...]:
        """Return the children of this block."""
        if self.in_notion:
            if self._children is None:
                self._children = self._gen_children_cache()
            children = tuple(self._children)  # we copy implicitly to allow deleting blocks while iterating over it
        elif isinstance(self.obj_ref, obj_blocks.Block) and hasattr(self.obj_ref.value, 'children'):
            children = tuple(Block.wrap_obj_ref(block) for block in self.obj_ref.value.children)
        else:
            children = ()
        return children

    def append(self, blocks: Block | Sequence[Block], *, after: Block | None = None) -> Self:
        """Append a block or a sequence of blocks to the content of this block."""
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


class CommentMixin(DataObject[DO], wraps=obj_blocks.DataObject):
    """Mixin for objects that can have comments and discussions."""

    _comments: list[Discussion] | None = None

    @staticmethod
    def _group_by_discussions(comments: list[Comment]) -> list[list[Comment]]:
        comments.sort(key=lambda comment: comment.discussion_id)
        grouped = [list(group) for _, group in itertools.groupby(comments, key=lambda comment: comment.discussion_id)]
        grouped.sort(key=lambda group: group[0].created_time)
        return grouped

    def _generate_comments_cache(self) -> list[Discussion]:
        """Generate the comments cache."""
        if self.is_deleted:
            msg = 'Cannot retrieve comments of a deleted block from Notion.'
            raise RuntimeError(msg)

        session = get_active_session()
        comment_objs = session.api.comments.list(self.obj_ref.id)
        comments = [Comment.wrap_obj_ref(comment_obj) for comment_obj in comment_objs]
        return [Discussion(comment_thread, parent=self) for comment_thread in self._group_by_discussions(comments)]

    @property
    def _discussions(self) -> tuple[Discussion, ...]:
        """Return comments of this block or page as list of discussions, i.e. threads of comments."""
        if self.in_notion:
            if self._comments is None:
                self._comments = self._generate_comments_cache()
            comments = tuple(self._comments)
        else:
            comments = ()
        return comments


BT = TypeVar('BT', bound=obj_blocks.Block)  # ToDo: Use new syntax when requires-python >= 3.12


class Block(CommentMixin, DataObject[BT], ABC, wraps=obj_blocks.Block):
    """Abstract Notion block.

    Parent class of all block types.
    """

    @property
    def discussions(self) -> tuple[Discussion, ...]:
        """Return comments of this block as list of discussions, i.e. threads of comments."""
        return self._discussions

    def reload(self) -> Self:
        """Reload the block from the API."""
        session = get_active_session()
        self.obj_ref = cast(BT, session.api.blocks.retrieve(self.id))
        return self

    def _update_in_notion(self, *, exclude_attrs: Sequence[str] | None = None) -> None:
        """Update the locally modified block on Notion."""
        if self.in_notion:
            session = get_active_session()
            # missing_ok=True to cover `Heading` which behave like `TextBlock` but have no `children` attribute
            obj_ref = del_nested_attr(self.obj_ref, exclude_attrs, inplace=False, missing_ok=True)
            self.obj_ref = cast(BT, session.api.blocks.update(obj_ref))

    def replace(self, blocks: Block | Sequence[Block]) -> None:
        """Replace this block with another block or blocks."""
        if not isinstance(blocks, Sequence):
            blocks = [blocks]

        if self.is_deleted:
            msg = 'Cannot replace a deleted block.'
            raise InvalidAPIUsageError(msg)

        for block in blocks:  # do complete sanity check first
            if block.in_notion:
                msg = f'Cannot replace with a block {block} that is already in Notion.'
                raise InvalidAPIUsageError(msg)

        if self.parent is not None and isinstance(self.parent, ChildrenMixin):
            for block in reversed(blocks):
                self.parent.append(block, after=self)
        else:
            msg = 'Cannot replace a block that has no parent.'
            raise InvalidAPIUsageError(msg)

        self.delete()

    def insert_after(self, blocks: Block | Sequence[Block]) -> None:
        """Insert a block or several blocks after this block."""
        if not isinstance(blocks, Sequence):
            blocks = [blocks]

        if self.is_deleted:
            msg = 'Cannot insert a block after a deleted block.'
            raise InvalidAPIUsageError(msg)

        for block in blocks:  # do complete sanity check first
            if block.in_notion:
                msg = f'Cannot insert block {block} that is already in Notion.'
                raise InvalidAPIUsageError(msg)

        if self.parent is not None and isinstance(self.parent, ChildrenMixin):
            for block in reversed(blocks):
                self.parent.append(block, after=self)
        else:
            msg = 'Cannot insert a block that has no parent.'
            raise InvalidAPIUsageError(msg)


AnyBlock: TypeAlias = Block[Any]
"""For type hinting purposes, especially for lists of blocks, i.e. list[AnyBlock], in user code."""


class TextBlock(Block[BT], ABC, wraps=obj_blocks.TextBlock):
    """Abstract Text block.

    Parent class of all text block types.
    """

    def __init__(self, text: str) -> None:
        super().__init__()
        self.obj_ref.value.rich_text = Text(text).obj_ref

    @property
    def rich_text(self) -> Text:
        """Return the text content of this text block."""
        rich_texts = self.obj_ref.value.rich_text
        return Text.wrap_obj_ref(rich_texts)

    @rich_text.setter
    def rich_text(self, text: str) -> None:
        # Right now this leads to a mypy error, see
        # https://github.com/python/mypy/issues/3004
        # Always pass `RichText` objects to this setter to avoid this error.
        self.obj_ref.value.rich_text = Text(text).obj_ref
        self._update_in_notion(exclude_attrs=['paragraph.children'])


class Code(TextBlock[obj_blocks.Code], wraps=obj_blocks.Code):
    """Code block."""

    def __init__(
        self,
        text: str,
        *,
        language: CodeLang = CodeLang.PLAIN_TEXT,
        caption: str | None = None,
    ) -> None:
        super().__init__(text)
        self.obj_ref.value.language = language
        self.obj_ref.value.caption = Text(caption).obj_ref if caption is not None else []

    @property
    def language(self) -> CodeLang:
        return self.obj_ref.value.language

    @language.setter
    def language(self, language: CodeLang) -> None:
        self.obj_ref.value.language = language
        self._update_in_notion()

    @property
    def caption(self) -> Text:
        return Text.wrap_obj_ref(self.obj_ref.value.caption)

    @caption.setter
    def caption(self, caption: str | None) -> None:
        self.obj_ref.value.caption = Text(caption).obj_ref if caption is not None else []
        self._update_in_notion()

    def to_markdown(self) -> str:
        lang = self.obj_ref.value.language
        return f'```{lang}\n{self.rich_text.to_markdown()}\n```'


class ColoredTextBlock(TextBlock[BT], ABC, wraps=obj_blocks.TextBlock):
    """Abstract Text block with color.

    Parent class of all text block types with color.
    """

    def __init__(
        self,
        text: str,
        *,
        color: Color | BGColor = Color.DEFAULT,
    ) -> None:
        super().__init__(text)
        self.obj_ref.value.rich_text = Text(text).obj_ref
        self.obj_ref.value.color = color

    @property
    def color(self) -> Color | BGColor:
        return self.obj_ref.value.color

    @color.setter
    def color(self, color: Color | BGColor) -> None:
        self.obj_ref.value.color = color
        self._update_in_notion(exclude_attrs=['paragraph.children'])


class Paragraph(ColoredTextBlock[obj_blocks.Paragraph], ChildrenMixin, wraps=obj_blocks.Paragraph):
    """Paragraph block."""

    def to_markdown(self) -> str:
        return f'{self.rich_text.to_markdown()}'


class Heading(ColoredTextBlock[BT], ChildrenMixin, ABC, wraps=obj_blocks.Heading):
    """Abstract Heading block.

    Parent class of all heading block types.
    """

    def __init__(
        self,
        text: str,
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

    def append(self, blocks: Block | Sequence[Block], *, after: Block | None = None) -> Self:
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
        text: str,
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
        match self.icon:
            case Emoji():
                return f'{self.icon} {self.rich_text.to_markdown()}\n'
            case FileInfo():
                return f'![icon]({self.icon.url}) {self.rich_text.to_markdown()}\n'
            case _:
                msg = f'Invalid icon type {type(self.icon)}'
                raise ValueError(msg)


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
        text: str,
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
    """Table of Contents block."""

    def __init__(self, *, color: Color | BGColor = Color.DEFAULT):
        super().__init__()
        self.obj_ref.value.color = color

    def to_markdown(self) -> str:  # noqa: PLR6301
        return '```{toc}\n```'


class Breadcrumb(Block[obj_blocks.Breadcrumb], wraps=obj_blocks.Breadcrumb):
    """Breadcrumb block."""

    def to_markdown(self) -> str:
        def is_page(obj: NotionEntity) -> TypeGuard[Page]:
            return obj.is_page

        return ' / '.join(ancestor.title for ancestor in self.ancestors if is_page(ancestor)) + '\n'


class Embed(Block[obj_blocks.Embed], wraps=obj_blocks.Embed):
    """Embed block."""

    def __init__(self, url: str, *, caption: str | None = None):
        super().__init__()
        self.obj_ref.value.url = url
        self.obj_ref.value.caption = Text(caption).obj_ref if caption is not None else None

    @property
    def url(self) -> str | None:
        """Return the URL of the embedded item."""
        return self.obj_ref.value.url

    @url.setter
    def url(self, url: str) -> None:
        self.obj_ref.value.url = url
        self._update_in_notion()

    @property
    def caption(self) -> Text:
        """Return the caption of the embedded item."""
        return Text.wrap_obj_ref(self.obj_ref.value.caption)

    @caption.setter
    def caption(self, caption: str | None) -> None:
        self.obj_ref.value.caption = Text(caption).obj_ref if caption is not None else []
        self._update_in_notion()

    def to_markdown(self) -> str:
        if self.url is not None:
            return f'[{self.url}]({self.url})\n'
        else:
            return ''


class Bookmark(Block[obj_blocks.Bookmark], wraps=obj_blocks.Bookmark):
    """Bookmark block."""

    def __init__(self, url: str, *, caption: str | None = None):
        super().__init__()
        self.obj_ref.value.url = url
        self.obj_ref.value.caption = Text(caption).obj_ref if caption is not None else None

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
    """Abstract Block for file-based blocks.

    Parent class of all file-based block types.
    """

    def __init__(
        self,
        url: str,
        *,
        caption: str | None = None,
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
    def caption(self) -> Text:
        return self.file_info.caption

    @caption.setter
    def caption(self, caption: str | None) -> None:
        self.obj_ref.value.caption = Text(caption).obj_ref if caption is not None else []
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
        caption: str | None = None,
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

    def __init__(self, url: str, *, caption: str | None = None):
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
        """Add a new column to this block of columns."""
        if 1 <= index <= len(self.children):
            new_col = Column.wrap_obj_ref(obj_blocks.Column.build())
            super().append(new_col, after=self.children[index - 1])
            return self
        else:
            msg = f'Columns can only be inserted from index 1 to {len(self.children)}.'
            raise IndexError(msg)

    def append(self, blocks: Block | Sequence[Block], *, after: Block | None = None) -> Self:  # noqa: PLR6301
        msg = 'Use `add_column` to append a new column.'
        raise InvalidAPIUsageError(msg)

    def to_markdown(self) -> str:
        cols = []
        for i, block in enumerate(self.children):
            md = md_comment(f'column {i + 1}')
            cols.append(md + block.to_markdown())
        return '\n'.join(cols)


class TableRow(tuple[Text, ...], Block[obj_blocks.TableRow], wraps=obj_blocks.TableRow):
    """Table row block behaving like a tuple."""

    def __new__(cls, *cells: str) -> TableRow:
        return tuple.__new__(cls, cells)

    def __init__(self, *cells: str):
        super().__init__(n_cells=len(cells))
        for idx, cell in enumerate(cells):
            self.obj_ref.table_row.cells[idx] = Text(cell).obj_ref

    @classmethod
    def wrap_obj_ref(cls, obj_ref: obj_blocks.TableRow, /) -> TableRow:
        row = TableRow(*[Text.wrap_obj_ref(cell) for cell in obj_ref.table_row.cells])
        row.obj_ref = obj_ref
        return row

    def to_markdown(self) -> str:
        return ' | '.join(self)


class Table(Block[obj_blocks.Table], ChildrenMixin, wraps=obj_blocks.Table):
    """Table block."""

    def __init__(self, n_rows: int, n_cols: int, *, header_col: bool = False, header_row: bool = False):
        super().__init__()
        self.obj_ref.table.table_width = n_cols
        self.obj_ref.table.has_column_header = header_row
        self.obj_ref.table.has_row_header = header_col
        self.obj_ref.table.children = [obj_blocks.TableRow.build(n_cols) for _ in range(n_rows)]
        self.obj_ref.has_children = bool(self.obj_ref.table.children)

    def _check_index(self, index: int | tuple[int, int]) -> tuple[int, int | None]:
        if isinstance(index, tuple):
            row_idx, col_idx = index
        else:
            row_idx, col_idx = index, None

        if not (0 <= row_idx < len(self.children)):
            msg = 'Row index out of range'
            raise IndexError(msg)

        if col_idx is not None and not (0 <= col_idx < self.width):
            msg = 'Column index out of range'
            raise IndexError(msg)

        return row_idx, col_idx

    def __str__(self) -> str:
        return self.to_markdown()

    @overload
    def __getitem__(self, index: int) -> TableRow: ...

    @overload
    def __getitem__(self, index: tuple[int, int]) -> Text: ...

    def __getitem__(self, index: int | tuple[int, int]) -> Text | TableRow:
        row_idx, col_idx = self._check_index(index)
        row = self.children[row_idx]
        return row if col_idx is None else row[col_idx]

    def __setitem__(
        self,
        index: int | tuple[int, int],
        value: str | Sequence[str],
    ) -> None:
        row_idx, col_idx = self._check_index(index)
        row = self.children[row_idx]
        row_obj = row.obj_ref
        if col_idx is None:
            if not isinstance(value, Sequence) or len(value) != self.width:
                msg = 'Value is no sequence or its length does not match the width of the table.'
                raise ValueError(msg)
            for idx, item in enumerate(value):
                row_obj.table_row.cells[idx] = Text(item).obj_ref
        elif isinstance(value, str):
            row_obj.table_row.cells[col_idx] = Text(value).obj_ref
        else:
            msg = 'A single value is needed to set a single cell.'
            raise ValueError(msg)
        row._update_in_notion()
        if self._children is not None:  # update cache
            self._children[row_idx] = TableRow.wrap_obj_ref(row_obj)  # needed to call __new__ on the TableRow

    @property
    def children(self) -> tuple[TableRow, ...]:
        """Return all rows of the table."""
        return tuple(cast(TableRow, block) for block in super().children)

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
    def has_header_row(self) -> bool:
        """Return whether the table has a header row."""
        return self.obj_ref.table.has_column_header

    @has_header_row.setter
    def has_header_row(self, header_row: bool) -> None:
        self.obj_ref.table.has_column_header = header_row
        self._update_in_notion(exclude_attrs=['table.table_width', 'table.children'])

    @property
    def has_header_col(self) -> bool:
        """Return whether the table has a header column."""
        return self.obj_ref.table.has_row_header

    @has_header_col.setter
    def has_header_col(self, header_col: bool) -> None:
        self.obj_ref.table.has_row_header = header_col
        self._update_in_notion(exclude_attrs=['table.table_width', 'table.children'])

    def to_markdown(self) -> str:
        """Return the table as Markdown."""
        headers = 'firstrow' if self.has_header_row else [''] * self.width
        return tabulate(self.children, headers, tablefmt='github') + '\n'

    def insert_row(self, index: int, values: Sequence[str]) -> Self:
        """Insert a new row at the given index."""
        if not (1 <= index <= len(self.children)):
            msg = f'Columns can only be inserted from index 1 to {len(self.children)}.'
            raise IndexError(msg)
        if len(values) != self.width:
            msg = 'Length of passed value does not match width of table.'
            raise ValueError(msg)

        self.append(TableRow(*values), after=self.children[index - 1])
        return self

    def append_row(self, values: Sequence[str]) -> Self:
        """Append a new row to the table."""
        return self.insert_row(len(self.children), values)


class LinkToPage(Block[obj_blocks.LinkToPage], wraps=obj_blocks.LinkToPage):
    """Link to page block.

    !!! note
        Updating a link to page block is not supported by the Notion API.
        Use `.replace(new_block)` instead.
    """

    def __init__(self, page: Page):
        super().__init__()
        self.obj_ref.link_to_page = objs.PageRef.build(page.obj_ref)

    @property
    def page(self) -> Page:
        session = get_active_session()
        return session.get_page(objs.get_uuid(self.obj_ref.link_to_page))

    @page.setter
    def page(self, page: Page) -> None:  # noqa: PLR6301
        # Updating a link to page block is not supported by the API and returns the current one.
        # self.obj_ref.link_to_page = objs.PageRef.build(page.obj_ref)
        # self._update_in_notion()
        msg = 'Updating a link to page block is not supported by the API. Use `.replace(new_block)` instead.'
        raise InvalidAPIUsageError(msg)

    def to_markdown(self) -> str:
        return f'[**↗️ <u>{self.page.title}</u>**]({self.page.url})\n'


class SyncedBlock(Block[obj_blocks.SyncedBlock], ChildrenMixin, wraps=obj_blocks.SyncedBlock):
    """Synced block - either original or synced."""

    def __init__(self, blocks: Block | Sequence[Block]):
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

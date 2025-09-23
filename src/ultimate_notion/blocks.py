"""Blocks that make up the content of a page.

Following blocks can be nested, i.e. they can contain children:

- Paragraph
- Headings if toggleable (*)
- Quote
- Callout
- BulletedItem
- NumberedItem
- ToDoItem
- ToggleItem
- Column within a Columns object (*)
- Table as list of TableRow objects (*)
- Synced Block
- Template (read-only)

Blocks with (*) don't have an official `children` field in the Notion API call but can still contain children using the
`append` method. They can also be created offline and populated with children offline before being pushed to Notion.
This is a technical detail and should not affect the user experience.
"""

from __future__ import annotations

import itertools
import mimetypes
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeGuard, cast, overload

import numpy as np
from notion_client import APIResponseError
from tabulate import tabulate
from typing_extensions import Self, TypeVar
from url_normalize import url_normalize

from ultimate_notion.comment import Comment, Discussion
from ultimate_notion.core import NotionEntity, get_active_session, get_url
from ultimate_notion.emoji import CustomEmoji, Emoji
from ultimate_notion.errors import InvalidAPIUsageError
from ultimate_notion.file import AnyFile, ExternalFile, NotionFile
from ultimate_notion.markdown import md_comment
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.core import UnsetType, raise_unset
from ultimate_notion.obj_api.enums import BGColor, CodeLang, Color
from ultimate_notion.rich_text import Text, User
from ultimate_notion.utils import set_attr_none

if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.page import Page


MIN_COLS = 2
"""Minimum number of columns when creating a column block to structure a page."""
MAX_BLOCK_CHILDREN = 100
""""The maximum number of block children that can be appended in one API call.

Source: https://developers.notion.com/reference/patch-block-children
"""
MAX_BLOCKS_PER_REQUEST = 1000
"""The maximum number of blocks that can be created/updated/deleted in one API request.

Source: https://developers.notion.com/reference/request-limits#limits-for-property-values
"""
MAX_NESTING_LEVEL = 2
"""The maximum nesting level of blocks in Notion for one append call."""

# ToDo: Use new syntax when requires-python >= 3.12
DO_co = TypeVar('DO_co', bound=obj_blocks.DataObject, default=obj_blocks.DataObject, covariant=True)


def wrap_icon(
    icon_obj: objs.FileObject | objs.EmojiObject | objs.CustomEmojiObject,
) -> NotionFile | ExternalFile | CustomEmoji | Emoji:
    """Wrap the icon object into the corresponding class."""
    match icon_obj:
        case objs.ExternalFile():
            return ExternalFile.wrap_obj_ref(icon_obj)
        case objs.HostedFile():
            return NotionFile.wrap_obj_ref(icon_obj)
        case objs.EmojiObject():
            return Emoji.wrap_obj_ref(icon_obj)
        case objs.CustomEmojiObject():
            return CustomEmoji.wrap_obj_ref(icon_obj)
        case _:
            msg = f'unknown icon object of {type(icon_obj)}'
            raise RuntimeError(msg)


class DataObject(NotionEntity[DO_co], wraps=obj_blocks.DataObject):
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
        last_edit_user_ref = raise_unset(self.obj_ref.last_edited_by)
        return session.get_user(raise_unset(last_edit_user_ref.id))

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
        self.obj_ref = cast(DO_co, session.api.blocks.delete(self.id))
        self._delete_me_from_parent()
        return self

    @property
    def is_deleted(self) -> bool:
        """Return wether the object is in trash."""
        return self.obj_ref.in_trash or self.obj_ref.archived

    @abstractmethod
    def to_markdown(self) -> str:
        """Return the content of the block as Markdown."""

    def _to_markdown(self) -> str:
        """Return the content of the block as Markdown.

        This method can be overridden to provide a custom Markdown representation,
        e.g. for a page/database child block.
        """
        return self.to_markdown()


class ChildrenMixin(DataObject[DO_co], wraps=obj_blocks.DataObject):
    """Mixin for data objects that can have children

    Note that we don't use the `children` property of some Notion objects, e.g. paragraph, quote, etc.,
    as not every object has this property, e.g. a page or toggleable heading. The `children` property
    is mostly used to send a nested batch of blocks with children to Notion in one API call. It cannot
    be trusted though that the `children` property is always up-to-date, e.g. when blocks are appended
    as the Notion API often doesn't send the `children` property back in the response.
    """

    _children: list[Block] | None = None

    @property
    def _has_children_field(self) -> bool:
        """Return whether the object has a `children` field."""
        return isinstance(self.obj_ref, obj_blocks.Block) and hasattr(self.obj_ref.value, 'children')

    def _gen_children_cache(self) -> list[Block]:
        """Generate the children cache."""
        if self.is_deleted:
            msg = 'Cannot retrieve children of a deleted block from Notion.'
            raise RuntimeError(msg)

        session = get_active_session()
        child_blocks_objs = list(session.api.blocks.children.list(parent=objs.get_uuid(self.obj_ref)))
        self.obj_ref.has_children = bool(child_blocks_objs)  # update the property manually to avoid API call
        if self._has_children_field:
            self.obj_ref.value.children = child_blocks_objs  # type: ignore[attr-defined] # update the children attribute

        child_blocks: list[Block] = [Block.wrap_obj_ref(block) for block in child_blocks_objs]

        for idx, child_block in enumerate(child_blocks):
            if isinstance(child_block, ChildPage):
                child_blocks[idx] = cast(Block, child_block.page)
            elif isinstance(child_block, ChildDatabase):
                try:
                    ref_block = cast(Block, child_block.db)
                except APIResponseError:
                    # linked database that cannot be retrieved via API. Check the docs:
                    # https://developers.notion.com/reference/retrieve-a-database
                    ref_block = cast(Block, child_block)
                child_blocks[idx] = ref_block

        return [cast(Block, session.cache.setdefault(block.id, block)) for block in child_blocks]

    @property
    def children(self) -> tuple[Block, ...]:
        """Return the children of this block."""
        if self.in_notion:
            if self._children is None:
                self._children = self._gen_children_cache()
            children = tuple(self._children)  # copy list to allow deleting blocks while iterating over it
        elif self._children is not None:
            children = tuple(self._children)
        else:
            children = ()
        return children

    def append(self, blocks: Block | Sequence[Block], *, after: Block | None = None, sync: bool | None = None) -> Self:
        """Append a block or a sequence of blocks to the content of this block.

        If *this* block is already in Notion, the blocks are appended directly to Notion, otherwise
        they are prepared to be appended in one batch call, later.
        Note that explicitely defining `sync` will not affect the append behaviour itself but will raise
        an error if it is not what was expected, e.g. `sync=True` when this block is not yet in Notion.

        Args:
            blocks: A block or a sequence of blocks to append.
            after: A block to append the new blocks after.
            sync: Whether to sync the changes with Notion directly or in one batch call later.
                  If `sync = None` (default), the blocks are appended directly if this block is already in Notion,
                  otherwise they are prepared to be appended in one batch call, later.
        """
        blocks = [blocks] if isinstance(blocks, Block) else blocks

        for block in blocks:
            if not isinstance(block, Block):
                msg = f'Cannot append {type(block)} to a block.'
                raise ValueError(msg)
            if block.in_notion:
                msg = 'Cannot append a block that is already in Notion.'
                raise InvalidAPIUsageError(msg)

        if self._children is None:
            self._children = self._gen_children_cache() if self.in_notion else []
        if not blocks:
            return self

        if sync is True and not self.in_notion:
            msg = 'Cannot append blocks synchronously to a block that is not in Notion.'
            raise InvalidAPIUsageError(msg)
        elif sync is False:
            if self.in_notion:
                msg = 'Cannot append asynchronously blocks to a block that is already in Notion.'
                raise InvalidAPIUsageError(msg)
            elif after is not None:
                msg = 'Appending asynchronously blocks after a specific block is not supported.'
                raise InvalidAPIUsageError(msg)
        elif not self.in_notion:
            if after is not None:
                msg = 'Cannot append blocks after a specific block if this block is not in Notion.'
                raise InvalidAPIUsageError(msg)
            self.obj_ref.has_children = True
            for block in blocks:
                block._parent = cast(Block, self)  # set fallback parent for offline use
            # Don't store it in the potential `children` field of the obj_ref and let the Notion API do it.
            self._children.extend(blocks)
        else:  # self.in_notion and sync is not False
            blocks_iter = _chunk_blocks_for_api(cast(ParentBlock, self), blocks)
            _append_block_chunks(blocks_iter, after=after)

        return self


class CommentMixin(DataObject[DO_co], wraps=obj_blocks.DataObject):
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
        comment_objs = session.api.comments.list(self.id)
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


# ToDo: Use new syntax when requires-python >= 3.12
B_co = TypeVar('B_co', bound=obj_blocks.Block, default=obj_blocks.Block, covariant=True)


class Block(CommentMixin[B_co], ABC, wraps=obj_blocks.Block):
    """Abstract Notion block.

    Parent class of all block types.
    """

    _parent: Block | Page | None = None  # fallback if block is not in Notion, e.g. offline assembly of blocks

    @property
    def parent(self) -> Block | Page | None:
        """Return the parent block or page, or None if not accessible."""
        from ultimate_notion.page import Page  # noqa: PLC0415  # Avoid circular import.

        if self.in_notion:
            return cast(Block | Page | None, super().parent)
        else:
            return self._parent

    @property
    def discussions(self) -> tuple[Discussion, ...]:
        """Return comments of this block as list of discussions, i.e. threads of comments."""
        return self._discussions

    def reload(self) -> Self:
        """Reload the block from the API."""
        session = get_active_session()
        self.obj_ref = cast(B_co, session.api.blocks.retrieve(self.id))
        return self

    def _update_in_notion(self, *, exclude_attrs: Sequence[str] | None = None) -> None:
        """Update the locally modified block on Notion."""
        if self.in_notion:
            session = get_active_session()
            # missing_ok=True below to cover `Heading` which behave like `TextBlock` but have no `children` attribute
            set_attr_none(self.obj_ref, exclude_attrs, inplace=True, missing_ok=True)
            session.api.blocks.update(self.obj_ref)

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
            self.parent.append(blocks, after=self)
        else:
            msg = 'Cannot insert a block that has no parent.'
            raise InvalidAPIUsageError(msg)

    def __eq__(self, other: Any | Block) -> bool:
        """Compare blocks by their content, not by their metadata like id, timestamp etc."""
        if not isinstance(other, Block):
            return NotImplemented
        return self.obj_ref.value == other.obj_ref.value

    def __hash__(self) -> int:
        return hash(self.obj_ref.value)


class ParentBlock(Block[B_co], ChildrenMixin[B_co], wraps=obj_blocks.Block):
    """A block that holds children blocks, mainly used for type checking.

    If there was no block like that, mypy would narrow a `Block | Page` object down to a Page object if we check
    for `isinstance(i, ChildrenMixin)` as Page inherits from ChildrenMixin and Block not. This is not what we want.
    """

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ParentBlock):
            if isinstance(other, Block):
                return False
            return NotImplemented

        return super().__eq__(other) and self.children == other.children

    def __hash__(self) -> int:
        return hash((super().__hash__(), *self.children))

    @classmethod
    def wrap_obj_ref(cls: type[Self], obj_ref: B_co, /) -> Self:  # type: ignore[misc] # breaking covariance
        self = super().wrap_obj_ref(obj_ref)
        if obj_ref.has_children and hasattr(self.obj_ref.value, 'children') and self.obj_ref.value.children:
            self._children = [Block.wrap_obj_ref(child) for child in self.obj_ref.value.children]
            self.obj_ref.value.children = []  # clear children to avoid confusion during comparison
        return self


class CaptionMixin(Block[B_co], wraps=obj_blocks.Block):
    """Mixin for objects that can have captions."""

    @property
    def caption(self) -> Text | None:
        """Return the caption of the code block."""
        if not isinstance(self.obj_ref.value, obj_blocks.CaptionMixin | objs.FileObject):
            msg = f'Block `{type(self).__name__}` with type data `{type(self.obj_ref.value).__name__}` has no caption.'
            raise RuntimeError(msg)
        if not (caption := self.obj_ref.value.caption):
            return None
        return Text.wrap_obj_ref(caption)

    @caption.setter
    def caption(self, caption: str | None) -> None:
        if not isinstance(self.obj_ref.value, obj_blocks.CaptionMixin | objs.FileObject):
            msg = f'Block `{type(self).__name__}` with type data `{type(self.obj_ref.value).__name__}` has no caption.'
            raise RuntimeError(msg)
        self.obj_ref.value.caption = Text(caption).obj_ref if caption is not None else []
        self._update_in_notion()


# ToDo: Use new syntax when requires-python >= 3.12
TB_co = TypeVar('TB_co', bound=obj_blocks.TextBlock, default=obj_blocks.TextBlock, covariant=True)


class TextBlock(Block[TB_co], ABC, wraps=obj_blocks.TextBlock):
    """Abstract Text block.

    Parent class of all text block types.
    """

    def __init__(self, text: str) -> None:
        super().__init__()
        self.obj_ref.value.rich_text = Text(text).obj_ref

    @property
    def rich_text(self) -> Text | None:
        """Return the text content of this text block."""
        if (rich_texts := self.obj_ref.value.rich_text) is None:
            return None
        return Text.wrap_obj_ref(rich_texts)

    @rich_text.setter
    def rich_text(self, text: str | None) -> None:
        # Right now this leads to a mypy error, see
        # https://github.com/python/mypy/issues/3004
        # Always pass `RichText` objects to this setter to avoid this error.
        if text is None:
            text = ''
        self.obj_ref.value.rich_text = Text(text).obj_ref
        self._update_in_notion(exclude_attrs=['paragraph.children'])

    def __str__(self) -> str:
        """Return the text content of this block as string."""
        return self.rich_text.to_plain_text() if self.rich_text else ''

    def to_markdown(self) -> str:
        """Return the text content of this block as Markdown."""
        if self.rich_text is None:
            return ''
        return self.rich_text.to_markdown()


class Code(TextBlock[obj_blocks.Code], CaptionMixin[obj_blocks.Code], wraps=obj_blocks.Code):
    """Code block."""

    def __init__(
        self,
        text: str,
        *,
        language: str | CodeLang = CodeLang.PLAIN_TEXT,
        caption: str | None = None,
    ) -> None:
        super().__init__(text)
        if not isinstance(language, CodeLang):
            language = CodeLang(language)
        self.obj_ref.value.language = language
        self.obj_ref.value.caption = Text(caption).obj_ref if caption is not None else []

    @property
    def language(self) -> CodeLang:
        """Return the programming language of the code block."""
        return self.obj_ref.value.language

    @language.setter
    def language(self, language: CodeLang) -> None:
        self.obj_ref.value.language = language
        self._update_in_notion()

    def to_markdown(self) -> str:
        """Return the code content of this block as Markdown."""
        lang = self.obj_ref.value.language
        return f'```{lang}\n{super().to_markdown()}\n```'


# ToDo: Use new syntax when requires-python >= 3.12
TB = TypeVar('TB', bound=obj_blocks.ColoredTextBlock)


class ColoredTextBlock(TextBlock[TB], wraps=obj_blocks.ColoredTextBlock):
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
        value = self._get_value()
        value.color = color

    def _get_value(self) -> obj_blocks.ColoredTextBlockTypeData:
        return self.obj_ref.value

    @property
    def color(self) -> Color | BGColor:
        """Return the color of the text block."""
        return self._get_value().color

    @color.setter
    def color(self, color: Color | BGColor) -> None:
        self._get_value().color = color
        self._update_in_notion(exclude_attrs=['paragraph.children'])


class Paragraph(ColoredTextBlock[obj_blocks.Paragraph], ParentBlock[obj_blocks.Paragraph], wraps=obj_blocks.Paragraph):
    """Paragraph block."""


# ToDo: Use new syntax when requires-python >= 3.12
HT = TypeVar('HT', bound=obj_blocks.Heading)


class Heading(ColoredTextBlock[HT], ParentBlock[obj_blocks.Heading], wraps=obj_blocks.Heading):
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

    def append(self, blocks: Block | Sequence[Block], *, after: Block | None = None, sync: bool | None = None) -> Self:
        if not self.toggleable:
            msg = 'Cannot append blocks to a non-toggleable heading.'
            raise InvalidAPIUsageError(msg)
        return super().append(blocks, after=after, sync=sync)


class Heading1(Heading[obj_blocks.Heading1], wraps=obj_blocks.Heading1):
    """Heading 1 block."""

    def to_markdown(self) -> str:
        return f'## {super().to_markdown()}'  # we use ## as # is used for page titles


class Heading2(Heading[obj_blocks.Heading2], wraps=obj_blocks.Heading2):
    """Heading 2 block."""

    def to_markdown(self) -> str:
        return f'### {super().to_markdown()}'


class Heading3(Heading[obj_blocks.Heading3], wraps=obj_blocks.Heading3):
    """Heading 3 block."""

    def to_markdown(self) -> str:
        return f'#### {super().to_markdown()}'


class Quote(ColoredTextBlock[obj_blocks.Quote], ParentBlock[obj_blocks.Quote], wraps=obj_blocks.Quote):
    """Quote block."""

    def to_markdown(self) -> str:
        return f'> {super().to_markdown()}\n'


class Callout(ColoredTextBlock[obj_blocks.Callout], ParentBlock[obj_blocks.Callout], wraps=obj_blocks.Callout):
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
        icon: AnyFile | str | Emoji | CustomEmoji | None = None,
    ) -> None:
        super().__init__(text, color=color)
        if isinstance(icon, str) and not isinstance(icon, Emoji | CustomEmoji):
            icon = Emoji(icon)
        if icon is None:
            # Use the Notion default icon instead of sending Unset, which would be replaced by Notion with their
            # default anyway. This will get us into trouble if Notion ever changes their default icon. But for now,
            # this is the best we can do for comparison etc.
            icon = self.get_default_icon()

        self.obj_ref.value.icon = icon.obj_ref

    @staticmethod
    def get_default_icon() -> Emoji:
        """Return the default icon of a callout block."""
        return Emoji('💡')

    @property
    def icon(self) -> NotionFile | ExternalFile | Emoji | CustomEmoji:
        if isinstance(icon := self.obj_ref.value.icon, UnsetType):
            return self.get_default_icon()
        else:
            return wrap_icon(icon)

    @icon.setter
    def icon(self, icon: AnyFile | Emoji | CustomEmoji | None) -> None:
        if icon is None:
            icon = self.get_default_icon()
        self.obj_ref.value.icon = icon.obj_ref
        self._update_in_notion()

    def to_markdown(self) -> str:
        match self.icon:
            case Emoji():
                return f'{self.icon} {super().to_markdown()}\n'
            case CustomEmoji():
                return f':{self.icon.name}: {super().to_markdown()}\n'
            case AnyFile():
                return f'![icon]({self.icon.url}) {super().to_markdown()}\n'
            case _:
                msg = f'Invalid icon type {type(self.icon)}'
                raise ValueError(msg)


class BulletedItem(
    ColoredTextBlock[obj_blocks.BulletedListItem],
    ParentBlock[obj_blocks.BulletedListItem],
    wraps=obj_blocks.BulletedListItem,
):
    """Bulleted list item."""

    def to_markdown(self) -> str:
        return f'- {super().to_markdown()}\n'


class NumberedItem(
    ColoredTextBlock[obj_blocks.NumberedListItem],
    ParentBlock[obj_blocks.NumberedListItem],
    wraps=obj_blocks.NumberedListItem,
):
    """Numbered list item."""

    def to_markdown(self) -> str:
        return f'1. {super().to_markdown()}\n'


class ToDoItem(ColoredTextBlock[obj_blocks.ToDo], ParentBlock[obj_blocks.ToDo], wraps=obj_blocks.ToDo):
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
        return f'- [{mark}] {super().to_markdown()}\n'


class ToggleItem(ColoredTextBlock[obj_blocks.Toggle], ParentBlock[obj_blocks.Toggle], wraps=obj_blocks.Toggle):
    """Toggle list item."""

    def to_markdown(self) -> str:
        return f'- {super().to_markdown()}\n'


class Divider(Block[obj_blocks.Divider], wraps=obj_blocks.Divider):
    """Divider block."""

    def to_markdown(self) -> str:  # noqa: PLR6301
        return '---\n'


class TableOfContents(Block[obj_blocks.TableOfContents], wraps=obj_blocks.TableOfContents):
    """Table of Contents block."""

    def __init__(self, *, color: Color | BGColor = Color.DEFAULT) -> None:
        super().__init__()
        self.obj_ref.value.color = color

    def to_markdown(self) -> str:  # noqa: PLR6301
        return '```{toc}\n```'


class Breadcrumb(Block[obj_blocks.Breadcrumb], wraps=obj_blocks.Breadcrumb):
    """Breadcrumb block."""

    def to_markdown(self) -> str:
        def is_page(obj: NotionEntity) -> TypeGuard[Page]:
            return obj.is_page

        return ' / '.join(ancestor.title or 'Untitled Page' for ancestor in self.ancestors if is_page(ancestor)) + '\n'


class Embed(CaptionMixin[obj_blocks.Embed], wraps=obj_blocks.Embed):
    """Embed block."""

    def __init__(self, url: str, *, caption: str | None = None) -> None:
        caption_obj = Text(caption).obj_ref if caption is not None else None
        super().__init__(url=url_normalize(url), caption=caption_obj)

    @property
    def url(self) -> str:
        """Return the URL of the embedded item."""
        return self.obj_ref.value.url

    @url.setter
    def url(self, url: str) -> None:
        if (norm_url := url_normalize(url)) is not None:
            self.obj_ref.value.url = norm_url
            self._update_in_notion()
        else:
            msg = f'Invalid URL: {url}'
            raise ValueError(msg)

    def to_markdown(self) -> str:
        title = self.caption.to_plain_text() if self.caption is not None else self.url
        if self.url is not None:
            return f'[{title}]({self.url})\n'
        else:
            return ''


class Bookmark(CaptionMixin[obj_blocks.Bookmark], wraps=obj_blocks.Bookmark):
    """Bookmark block."""

    def __init__(self, url: str, *, caption: str | None = None) -> None:
        caption_obj = Text(caption).obj_ref if caption is not None else None
        super().__init__(url=url_normalize(url), caption=caption_obj)

    @property
    def url(self) -> str | None:
        """Return the URL of the bookmark."""
        if url := self.obj_ref.value.url:
            return url
        return None

    @url.setter
    def url(self, url: str | None) -> None:
        url = url_normalize(url)
        self.obj_ref.value.url = '' if url is None else url
        self._update_in_notion()

    def to_markdown(self) -> str:
        title = self.caption.to_plain_text() if self.caption is not None else self.url
        if self.url is not None:
            return f'Bookmark: [{title}]({self.url})\n'
        else:
            return 'Bookmark: [Add a web bookmark]()\n'  # emtpy bookmark


class LinkPreview(Block[obj_blocks.LinkPreview], wraps=obj_blocks.LinkPreview):
    """Link preview block.

    !!! warning "Not Supported"

        The `link_preview` block can only be returned as part of a response.
        The Notion API does not support creating or appending `link_preview` blocks.
    """

    def __init__(self, url: str) -> None:
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

    def __init__(self, latex: str) -> None:
        super().__init__()
        self.obj_ref.value.expression = latex

    @property
    def latex(self) -> str:
        """Return the LaTeX expression of the equation."""
        if (expr := self.obj_ref.equation.expression) is not None:
            return expr.rstrip()
        else:
            return ''

    @latex.setter
    def latex(self, latex: str) -> None:
        self.obj_ref.value.expression = latex
        self._update_in_notion()

    def to_markdown(self) -> str:
        """Return the LaTeX expression of the equation as Markdown."""
        return f'$$\n{self.latex}\n$$\n'


FT = TypeVar('FT', bound=obj_blocks.FileBase)


class FileBaseBlock(CaptionMixin[FT], ABC, wraps=obj_blocks.FileBase):
    """Abstract Block for file-based blocks.

    Parent class of all file-based block types.
    """

    def __init__(
        self,
        file: AnyFile,
        *,
        caption: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__()
        if isinstance(file, str):
            msg = 'Expected a file object! Use `uno.url` or upload a local file first.'
            raise ValueError(msg)

        file.name = name if name is not None else file.name
        file.caption = caption if caption is not None else file.caption
        self.obj_ref.value = file.obj_ref

    @property
    def file_info(self) -> AnyFile:
        """Return the file information of this block as a copy."""
        if isinstance(file_obj := self.obj_ref.value, objs.FileObject):
            return AnyFile.wrap_obj_ref(file_obj.model_copy(deep=True))
        else:
            msg = f'Unknown file type {type(file_obj)}'
            raise ValueError(msg)

    @property
    def url(self) -> str:
        """Return the URL of the file."""
        if isinstance(file_info := self.file_info, NotionFile | ExternalFile):
            return file_info.url
        else:
            msg = f'File type {type(file_info)} has no URL.'
            raise ValueError(msg)


class File(FileBaseBlock[obj_blocks.File], wraps=obj_blocks.File):
    """File block.

    !!! note

        Only the caption and name can be modified, the file object is read-only.
        Note that only the file name not the file suffix can be modified,
        the suffix is determined initially by the url.
    """

    def __init__(
        self,
        file: AnyFile,
        *,
        name: str | None = None,
        caption: str | None = None,
    ) -> None:
        super().__init__(file, caption=caption, name=name)

    @property
    def name(self) -> str:
        """Return the name of the file."""
        name = self.file_info.name
        return name if name is not None else ''

    @name.setter
    def name(self, name: str) -> None:
        self.obj_ref.value.name = name
        self._update_in_notion()

    def to_markdown(self) -> str:
        """Return the file link as Markdown."""
        md = f'[📎 {self.name}]({self.url})\n'
        if self.caption is not None:
            md += f'{self.caption.to_markdown()}\n'
        return md


class Image(FileBaseBlock[obj_blocks.Image], wraps=obj_blocks.Image):
    """Image block.

    !!! note

        Only the caption can be modified, the URL is read-only.
    """

    def __init__(self, file: AnyFile, *, caption: str | None = None) -> None:
        super().__init__(file, caption=caption)

    def to_markdown(self) -> str:
        """Return the image as Markdown."""
        alt = self.url.rsplit('/').pop()
        if self.caption is not None:
            caption = self.caption.to_plain_text()
            return f'<figure><img src="{self.url}" alt="{alt}" /><figcaption>{caption}</figcaption></figure>\n'
        else:
            return f'![{alt}]({self.url})\n'


class PDF(FileBaseBlock[obj_blocks.PDF], wraps=obj_blocks.PDF):
    """PDF block.

    !!! note

        Only the caption can be modified, the URL is read-only.
    """

    def __init__(self, file: AnyFile, *, caption: str | None = None) -> None:
        file.name = None  # PDF files cannot have a name
        super().__init__(file, caption=caption)

    def to_markdown(self) -> str:
        """Return the PDF as Markdown."""
        name = self.url.rsplit('/').pop()
        md = f'[📖 {name}]({self.url})\n'
        if self.caption:
            md += f'{self.caption.to_markdown()}\n'
        return md


class Video(FileBaseBlock[obj_blocks.Video], wraps=obj_blocks.Video):
    """Video block.

    !!! note

        Only the caption can be modified, the URL is read-only.
    """

    def __init__(self, file: AnyFile, *, caption: str | None = None) -> None:
        file.name = None  # Video files cannot have a name
        super().__init__(file, caption=caption)

    def to_markdown(self) -> str:
        """Return the video as Markdown."""
        mime_type, _ = mimetypes.guess_type(self.url)
        vtype = f' type="{mime_type}"' if mime_type else ''
        caption = '' if self.caption is None else self.caption.to_markdown()
        md = f'<video width="320" height="240" controls><source src="{self.url}"{vtype}>{caption}</video>\n'
        return md


class Audio(FileBaseBlock[obj_blocks.Audio], wraps=obj_blocks.Audio):
    """Audio block.

    !!! note

        Only the caption can be modified, the URL is read-only.
    """

    def __init__(self, file: AnyFile, *, caption: str | None = None) -> None:
        file.name = None  # Audio files cannot have a name
        super().__init__(file, caption=caption)

    def to_markdown(self) -> str:
        """Return the audio as Markdown."""
        mime_type, _ = mimetypes.guess_type(self.url)
        atype = f' type="{mime_type}"' if mime_type else ''
        caption = '' if self.caption is None else self.caption.to_markdown()
        md = f'<audio controls><source src="{self.url}"{atype}>{caption}</audio>\n'
        return md


class ChildPage(Block[obj_blocks.ChildPage], wraps=obj_blocks.ChildPage):
    """Child page block.

    !!! note

        To create a child page block, create a new page with the corresponding parent.
        This block is used only internally.
    """

    def __init__(self) -> None:
        msg = 'To create a child page block, create a new page with the corresponding parent.'
        raise InvalidAPIUsageError(msg)

    @property
    def title(self) -> str | None:
        """Return the title of the child page."""
        if title := raise_unset(self.obj_ref.child_page.title):
            return title
        return None

    @property
    def page(self) -> Page:
        """Return the actual Page object."""
        sess = get_active_session()
        return sess.get_page(self.id)

    def to_markdown(self) -> str:  # noqa: PLR6301
        msg = '`ChildPage` is only used internally, work with a proper `Page` instead.'
        raise InvalidAPIUsageError(msg)


class ChildDatabase(Block[obj_blocks.ChildDatabase], wraps=obj_blocks.ChildDatabase):
    """Child database block.

    This block is used to represent a database if it is a child of e.g. a page.
    We try to resolve it via the API to get the actual database object. This does not work
    if it is a `linked database` as mentioned in the Notion API docs:
    https://developers.notion.com/reference/retrieve-a-database

    !!! note

        To create a child database block as an end-user, create a new database with the corresponding parent.
        This block is used only internally.
    """

    def __init__(self) -> None:
        msg = 'To create a child database block, create a new database with the corresponding parent.'
        raise InvalidAPIUsageError(msg)

    @property
    def title(self) -> str | None:
        """Return the title of the child database"""
        if title := raise_unset(self.obj_ref.child_database.title):
            return title
        return None

    @property
    def db(self) -> Database:
        """Return the actual Database object."""
        sess = get_active_session()
        return sess.get_db(self.id)

    def to_markdown(self) -> str:  # noqa: PLR6301
        """Return the child database as Markdown."""
        return '<kbd>↗️ Linked database (unsupported)</kbd>'


class Column(ParentBlock[obj_blocks.Column], wraps=obj_blocks.Column):
    """Column block."""

    def __init__(self) -> None:
        msg = 'Column blocks cannot be created directly. Use `Columns` instead.'
        raise InvalidAPIUsageError(msg)

    def to_markdown(self) -> str:
        """Return the content of this column as Markdown."""
        mds = []
        for block in self.children:
            mds.append(block.to_markdown())
        return '\n'.join(mds)

    @property
    def width_ratio(self) -> float | None:
        """Return the width ratio of this column."""
        return self.obj_ref.column.width_ratio


class Columns(ParentBlock[obj_blocks.ColumnList], wraps=obj_blocks.ColumnList):
    """Columns block holding multiple `Column` blocks.

    This block is used to create a layout with multiple columns in a single page.
    Either specify the number of columns as an integer or provide a sequence of width ratios,
    which can be positive integers or floats.
    """

    def __init__(self, columns: int | Sequence[float | int]) -> None:
        """Create a new `Columns` block with the given number of columns."""
        super().__init__()
        match columns:
            case int() as n_columns:
                if n_columns < MIN_COLS:
                    msg = f'Number of columns must be at least {MIN_COLS}.'
                    raise ValueError(msg)
                self.obj_ref.column_list.children = [obj_blocks.Column.build() for _ in range(n_columns)]
            case ratios if isinstance(ratios, Sequence) and all(isinstance(x, float | int) for x in ratios):
                if not ratios or any(r <= 0 for r in ratios):
                    msg = 'Ratios must be a non-empty sequence of positive numbers.'
                    raise ValueError(msg)
                ratios_arr = np.array(ratios, dtype=float)
                ratios_arr /= ratios_arr.sum()  # normalize ratios to sum to 1 as asked by the Notion API
                self.obj_ref.column_list.children = [obj_blocks.Column.build(width_ratio=ratio) for ratio in ratios_arr]
            case _:
                msg = 'Columns must be initialized with an integer or a sequence of floats/integers.'
                raise TypeError(msg)

    def __getitem__(self, index: int) -> Column:
        return cast(Column, self.children[index])

    def add_column(self, index: int | None = None) -> Self:
        """Add a new column to this block of columns at the given index.

        The index must be between 0 and the number of columns (inclusive).
        If no index is given, the new column is added at the end.

        To specify the width ratio of the new column, use the `width_ratios` property.
        """
        if index is None:
            index = len(self.children)
        if 0 <= index <= len(self.children):
            new_col = Column.wrap_obj_ref(obj_blocks.Column.build())
            super().append(new_col, after=self.children[index - 1] if index > 0 else None)
            return self
        else:
            msg = f'Column index must be between 0 and {len(self.children)} (inclusive).'
            raise IndexError(msg)

    def append(self, blocks: Block | Sequence[Block], *, after: Block | None = None, sync: bool | None = None) -> Self:  # noqa: PLR6301
        """Append a block or a sequence of blocks to the content of this block."""
        msg = 'Use `add_column` to append a new column.'
        raise InvalidAPIUsageError(msg)

    def to_markdown(self) -> str:
        """Return the content of all columns as Markdown."""
        cols = []
        for i, block in enumerate(self.children):
            md = md_comment(f'column {i + 1}')
            cols.append(md + block.to_markdown())
        return '\n'.join(cols)

    @property
    def width_ratios(self) -> tuple[float | None, ...]:
        """Return the width ratios of the columns."""
        return tuple(cast(Column, col).width_ratio for col in self.children)

    @width_ratios.setter
    def width_ratios(self, ratios: Sequence[float | int]) -> None:
        """Set the width ratios of the columns."""
        if len(ratios) != len(self.children):
            msg = f'Ratios must have the same length as the number of columns ({len(self.children)}).'
            raise ValueError(msg)

        if not isinstance(ratios, Sequence) or not all(isinstance(x, float | int) for x in ratios):
            msg = 'Ratios must be a sequence of floats or integers.'
            raise TypeError(msg)
        if not ratios or any(r <= 0 for r in ratios):
            msg = 'Ratios must be a non-empty sequence of positive numbers.'
            raise ValueError(msg)

        ratios_arr = np.array(ratios, dtype=float)
        ratios_arr /= ratios_arr.sum()  # normalize ratios to sum to 1 as asked by the Notion API
        for col, ratio in zip(self.children, ratios_arr, strict=False):
            obj_ref = cast(obj_blocks.Column, col.obj_ref)
            obj_ref.column.width_ratio = ratio
            col._update_in_notion(exclude_attrs=['column.children'])


class TableRow(tuple[Text | None, ...], Block[obj_blocks.TableRow], wraps=obj_blocks.TableRow):
    """Table row block behaving like a tuple."""

    def __new__(cls, *cells: str | None) -> TableRow:
        return tuple.__new__(cls, cells)

    def __init__(self, *cells: str | None) -> None:
        super().__init__(n_cells=len(cells))
        for idx, cell in enumerate(cells):
            if cell is None:
                cell = ''
            self.obj_ref.table_row.cells[idx] = Text(cell).obj_ref

    @classmethod
    def wrap_obj_ref(cls, obj_ref: obj_blocks.TableRow, /) -> TableRow:
        row = TableRow(*[Text.wrap_obj_ref(cell) if cell else None for cell in obj_ref.table_row.cells])
        row.obj_ref = obj_ref
        return row

    def to_markdown(self) -> str:
        """Return the row as Markdown."""
        return ' | '.join(s or '' for s in self)  # convert None to ''


class Table(ParentBlock[obj_blocks.Table], wraps=obj_blocks.Table):
    """Table block."""

    def __init__(self, n_rows: int, n_cols: int, *, header_col: bool = False, header_row: bool = False) -> None:
        if n_rows < 1:
            msg = 'Table must have at least one row.'
            raise InvalidAPIUsageError(msg)
        if not (1 <= n_cols <= MAX_BLOCK_CHILDREN):
            msg = f'Number of columns must be between 1 and {MAX_BLOCK_CHILDREN}.'
            raise InvalidAPIUsageError(msg)

        super().__init__()
        self.obj_ref.table.table_width = n_cols
        self.obj_ref.table.has_column_header = header_row
        self.obj_ref.table.has_row_header = header_col
        self.obj_ref.has_children = True
        self._children = [TableRow.wrap_obj_ref(obj_blocks.TableRow.build(n_cols)) for _ in range(n_rows)]

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
    def __getitem__(self, index: tuple[int, int]) -> Text | None: ...

    def __getitem__(self, index: int | tuple[int, int]) -> Text | TableRow | None:
        row_idx, col_idx = self._check_index(index)
        row = self.children[row_idx]
        return row if col_idx is None else row[col_idx]

    def __setitem__(
        self,
        index: int | tuple[int, int],
        value: str | Sequence[str | None] | None,
    ) -> None:
        row_idx, col_idx = self._check_index(index)
        row = self.children[row_idx]
        row_obj = row.obj_ref
        if col_idx is None:
            if not isinstance(value, Sequence) or len(value) != self.width:
                msg = 'Value is no sequence or its length does not match the width of the table.'
                raise ValueError(msg)
            if isinstance(value, str):
                msg = 'A sequence of values is needed to set a whole row.'
                raise ValueError(msg)
            for idx, item in enumerate(value):
                item = item if item is not None else ''
                row_obj.table_row.cells[idx] = Text(item).obj_ref
        elif isinstance(value, str):
            value = value if value is not None else ''
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

    def __init__(self, page: Page) -> None:
        page_ref = objs.PageRef.build(page.obj_ref)
        super().__init__(link_to_page=page_ref)

    @property
    def page(self) -> Page:
        """Return the page this block links to."""
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
        """ "Return the link to page block as Markdown."""
        return f'[**↗️ <u>{self.page.title}</u>**]({self.page.url})\n'


class SyncedBlock(ParentBlock[obj_blocks.SyncedBlock], wraps=obj_blocks.SyncedBlock):
    """Synced block - either original or synced."""

    def __init__(self, blocks: Block | Sequence[Block]) -> None:
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
        """Return the content of this synced block as Markdown."""
        if self.is_original:
            md = md_comment('original block') if with_comment else ''
            md += '\n'.join([child.to_markdown() for child in self.children])
        else:
            md = md_comment('synced block') if with_comment else ''
            md += self.get_original().to_markdown(with_comment=False)
        return md


class Template(TextBlock[obj_blocks.Template], ParentBlock[obj_blocks.Template], wraps=obj_blocks.Template):
    """Template block.

    !!! warning "Deprecated"

        As of March 27, 2023 creation of template blocks will no longer be supported.
    """

    def __init__(self) -> None:
        msg = 'A template block cannot be created by a user.'
        raise InvalidAPIUsageError(msg)

    def to_markdown(self) -> str:
        """Return the template content as Markdown."""
        return f'<button type="button">{super().to_markdown()}</button>\n'


class Unsupported(Block[obj_blocks.UnsupportedBlock], wraps=obj_blocks.UnsupportedBlock):
    """Unsupported block in the API.

    Some blocks like buttons, AI blocks, or templates are not supported by the Notion API.
    They will be returned as `Unsupported` blocks when fetched, but cannot be created or modified.
    """

    def __init__(self) -> None:
        msg = 'An unsupported block cannot be created by a user.'
        raise InvalidAPIUsageError(msg)

    def to_markdown(self) -> str:  # noqa: PLR6301
        """Return a placeholder for unsupported blocks."""
        return '<kbd>Unsupported block</kbd>\n'


def traverse_blocks(blocks: Sequence[Block]) -> Iterator[Block]:
    """Recursively traverse blocks and their children in depth-first order."""
    for block in blocks:
        yield block
        if block.has_children and isinstance(block, ChildrenMixin):
            yield from traverse_blocks(block.children)


@dataclass
class _Node:
    """Tree of nodes used to chunk blocks for the Notion API."""

    block: Block | Page
    is_root: bool = False
    children: list[_Node] = field(default_factory=list)


def _chunk_blocks_for_api(parent: Block | Page, blocks: Sequence[Block]) -> Iterator[_Node]:
    """Yield batches of blocks with a parent so that each batch fulfills the Notion API requirements.

    Requirements:
    - Maximum of 1000 blocks per request
    - Maximum of 100 blocks in an array, also when appending children of a block
    - Maximum nesting level of 2, i.e. great grandchildren are not allowed

    We won't adhere to the 500KB limit per request here, as this is hard to check without
    knowing the exact size of the serialized request. If you hit this limit, reduce the number
    of blocks you append at once. This is quite unlikely to happen in practice as the current implementation
    appends only single-level blocks at a time adhering to the 100 blocks per array limit.

    Source: https://developers.notion.com/reference/request-limits#limits-for-property-values
    """
    # Breadth-first traversal to create batches of blocks which handles special blocks like columns and tables correctly
    # Note that there are a few edge cases where this can still fail, e.g. a table with >100 rows or many tables with
    # a total of more than 1000 rows/blocks. These cases are quite unlikely in practice.
    batch = _Node(block=parent, is_root=True)
    batch_blocks = [_Node(block=block) for block in blocks]
    queue = deque([(batch, batch_blocks)])
    while queue:
        batch, batch_blocks = queue.popleft()
        if not batch_blocks:
            continue

        curr_nodes, next_nodes = batch_blocks[:MAX_BLOCK_CHILDREN], batch_blocks[MAX_BLOCK_CHILDREN:]
        batch.children.extend(curr_nodes)

        for node in curr_nodes:
            match node.block:
                case Columns() as cols:
                    col_nodes = [_Node(block=col) for col in cols.children]
                    node.children.extend(col_nodes)
                    for col_node in col_nodes:
                        queue.append(
                            (col_node, [_Node(block=child) for child in cast(Column, col_node.block).children])
                        )
                case Table() as table:
                    node.children.extend([_Node(block=row) for row in table.children])
                case ParentBlock() as parent_block if parent_block.has_children:
                    queue.append((node, [_Node(block=child) for child in parent_block.children]))
        if next_nodes:
            queue.append((_Node(block=batch.block, is_root=batch.is_root), next_nodes))
        yield batch


def _build_obj_ref(node: _Node) -> Block:
    """Recursively build the obj_ref of a block and its children."""
    block = node.block
    children = node.children
    if not isinstance(block, Block):
        msg = f'Non-block type {type(block)} not allowed on this level of the hierarchy.'
        raise TypeError(msg)
    if isinstance(block, ParentBlock) and block.has_children and hasattr(block.obj_ref.value, 'children'):
        for child in node.children:
            _build_obj_ref(child)
        block.obj_ref.value.children = [child.block.obj_ref for child in children]
    return block


def _append_block_chunks(batch_trees: Iterator[_Node], *, after: Block | None = None) -> None:
    """Append chunks of blocks to a parent block, respecting API limits."""
    session = get_active_session()
    curr_after = after

    for parent_node in batch_trees:
        parent = parent_node.block
        blocks = [_build_obj_ref(child) for child in parent_node.children]

        after = curr_after if parent_node.is_root and curr_after is not None else None

        block_objs = [block.obj_ref for block in blocks]
        after_obj = None if after is None else after.obj_ref
        block_objs, after_block_objs = session.api.blocks.children.append(parent.obj_ref, block_objs, after=after_obj)
        parent.obj_ref.has_children = True

        if parent_node.is_root and isinstance(parent, ChildrenMixin):
            parent._children = [] if parent._children is None else parent._children
            # update the parent's children cache
            if after is None:
                parent._children.extend(blocks)
            else:
                insert_idx = next(idx for idx, block in enumerate(parent._children) if block.id == after.id) + 1
                # we also update the blocks after the position we inserted.
                for block, updated_block_obj in zip(parent._children[insert_idx:], after_block_objs, strict=True):
                    block.obj_ref.update(**updated_block_obj.model_dump())
                parent._children[insert_idx:insert_idx] = blocks
                curr_after = blocks[-1]  # update to the last inserted block to continue appending after it

        for block_node, block_obj in zip(parent_node.children, block_objs, strict=True):
            # update the appended blocks with the returned objects from the API. This only works at the top level.
            block_node.block.obj_ref.update(**block_obj.model_dump())
            session.cache[block_node.block.id] = block_node.block
            if block_node.children:  # we need to update explicitly the first level for Table, Columns, etc.
                child_objs = session.api.blocks.children.list(block_node.block.obj_ref)
                for child_node, child_obj in zip(block_node.children, child_objs, strict=True):
                    child_node.block.obj_ref.update(**child_obj.model_dump())
                    session.cache[child_node.block.id] = child_node.block

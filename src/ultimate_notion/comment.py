"""Comments and discussions for pages, blocks, and databases."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, overload
from uuid import UUID

from typing_extensions import Self

from ultimate_notion.core import NotionEntity, get_active_session
from ultimate_notion.errors import InvalidAPIUsageError
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.rich_text import Text
from ultimate_notion.user import User

if TYPE_CHECKING:
    from ultimate_notion.blocks import DataObject


class Comment(NotionEntity[objs.Comment], wraps=objs.Comment):
    """A comment on a page, block, or database behaving like a normal string."""

    @property
    def text(self) -> Text | None:
        """The text of the comment."""
        if (rt := self.obj_ref.rich_text) is None:
            return None
        return Text.wrap_obj_ref(rt)

    @property
    def user(self) -> User:
        """The user who created the comment."""
        return self.created_by

    @property
    def discussion_id(self) -> UUID:
        """The ID of the discussion thread that this comment belongs to."""
        return self.obj_ref.discussion_id

    def __str__(self) -> str:
        if self.text is None:
            return ''
        return str(self.text)

    def __repr__(self) -> str:
        return f'Comment("{self.user}", "{self!s}")'


class Discussion(Sequence[Comment]):
    """A list of comments, i.e. a discussion thread."""

    def __init__(self, comments: Sequence[Comment], *, parent: DataObject) -> None:
        self._comments = list(comments)
        self._parent = parent

    @overload
    def __getitem__(self, idx: int, /) -> Comment: ...

    @overload
    def __getitem__(self, idx: slice, /) -> Sequence[Comment]: ...

    def __getitem__(self, idx: int | slice, /) -> Comment | Sequence[Comment]:
        return self._comments[idx]

    def __len__(self) -> int:
        return len(self._comments)

    def __repr__(self) -> str:
        return f'Discussion({self._comments})'

    def __str__(self) -> str:
        return '\n'.join(f'{self.user}: {self.text}' for self in self._comments)

    def append(self, text: str) -> Self:
        """Add a comment to the discussion.

        !!! note

            This functionality requires that your integration was granted *insert* comment capabilities.

        """
        if self._parent.is_deleted:
            msg = 'Cannot add a comment to a deleted parent.'
            raise RuntimeError(msg)

        if not self._parent.in_notion:
            msg = 'Cannot add a comment to a parent that is not in Notion.'
            raise RuntimeError(msg)

        text = Text(text)
        session = get_active_session()

        if self._parent.is_page:
            comment = session.api.comments.create(page=self._parent.id, rich_text=text.obj_ref)
        elif self:  # parent is a block that already has comments
            comment = session.api.comments.append(
                rich_text=text.obj_ref, discussion_id=self._comments[-1].discussion_id
            )
        else:
            msg = 'Cannot create a new discussion thread for a block, only append to an existing discussion.'
            raise InvalidAPIUsageError(msg)

        self._comments.append(Comment.wrap_obj_ref(comment))
        return self

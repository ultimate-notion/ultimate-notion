"""Functions and classes for working with users in Notion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ultimate_notion.core import Wrapper, get_repr
from ultimate_notion.obj_api import objects as objs

if TYPE_CHECKING:
    from uuid import UUID


class WorkSpaceInfo(objs.WorkSpaceLimits):
    """Workspace information for a bot user."""

    name: str


class User(Wrapper[objs.User], wraps=objs.User):
    """User object for persons, bots and unknown users.

    Unknown users are users, which no longer participate in the workspace
    or were revoked access. They are represented by their ID and have
    the name `Unknown User`.
    """

    @classmethod
    def wrap_obj_ref(cls, obj_ref: objs.User) -> User:
        self = cls.__new__(cls)
        self.obj_ref = obj_ref
        return self

    def __str__(self) -> str:
        return self.name or f'Unnamed user {self.id}>'

    def __repr__(self) -> str:
        return get_repr(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, User):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def id(self) -> UUID:
        """Return the ID of this user."""
        return self.obj_ref.id

    @property
    def name(self) -> str | None:
        """Return the name of this user."""
        return self.obj_ref.name

    @property
    def is_person(self) -> bool:
        """Return True if this user is a person."""
        return isinstance(self.obj_ref, objs.Person)

    @property
    def is_bot(self) -> bool:
        """Return True if this user is a bot."""
        return isinstance(self.obj_ref, objs.Bot)

    @property
    def is_unknown(self) -> bool:
        """Return True if this user is an unknown user."""
        return isinstance(self.obj_ref, objs.UnknownUser)

    @property
    def avatar_url(self) -> str | None:
        """Return the avatar URL of this user."""
        return self.obj_ref.avatar_url

    @property
    def workspace_info(self) -> WorkSpaceInfo | None:
        """Return the workspace info of this bot, if available."""
        if isinstance(self.obj_ref, objs.Bot):
            kwargs = self.obj_ref.bot.workspace_limits.model_dump()
            return WorkSpaceInfo(name=self.obj_ref.bot.workspace_name, **kwargs)
        else:
            return None

    @property
    def email(self) -> str | None:
        """Return the e-mail address of this user, if available."""
        if isinstance(self.obj_ref, objs.Person):
            return self.obj_ref.person.email
        else:  # it's a bot or unknown without an e-mail
            return None

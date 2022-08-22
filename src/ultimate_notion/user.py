"""Wrapper for Notion user objects."""

import logging
from enum import Enum
from typing import Optional
from uuid import UUID

from .core import DataObject, NestedObject

log = logging.getLogger(__name__)


class UserType(str, Enum):
    """Available user types."""

    PERSON = "person"
    BOT = "bot"


class User(DataObject):
    """Represents a User in Notion."""

    # XXX why isn't this a TypedObject ?

    id: UUID
    object: str = "user"
    type: Optional[UserType] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None

    @classmethod
    def parse_obj(cls, obj):
        """Attempt to parse the given object data into the correct `User` type."""

        if obj is None:
            return None

        if "type" in obj:
            if obj["type"] == "person":
                return Person(**obj)

            if obj["type"] == "bot":
                return Bot(**obj)

        return cls(obj)


class Person(User):
    """Represents a Person in Notion."""

    class _NestedData(NestedObject):
        email: str

    person: _NestedData = None

    def __str__(self):
        """Return a string representation of this `Person`."""
        return f"[@{self.name}]"


class Bot(User):
    """Represents a Bot in Notion."""

    class _NestedData(NestedObject):
        pass

    bot: _NestedData = None

    def __str__(self):
        """Return a string representation of this `Bot`."""
        return f"[%{self.name}]"

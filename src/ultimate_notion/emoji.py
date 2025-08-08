"""Dealing with emoji objects of the Notion API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar
from uuid import UUID

from emoji import demojize, emojize, is_emoji

from ultimate_notion.core import Wrapper, get_repr
from ultimate_notion.errors import InvalidAPIUsageError
from ultimate_notion.obj_api import objects as objs

TO = TypeVar('TO', bound=objs.TypedObject)


class EmojiBase(Wrapper[TO], str, ABC, wraps=objs.TypedObject):
    """Base class for emoji objects, which behave like str."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the emoji."""
        raise NotImplementedError

    @property
    def to_code(self) -> str:
        """Represent the emoji as :shortcode:, e.g. :smile:"""
        return f':{self.name}:'

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, EmojiBase | str):
            return str(self) == str(other)
        else:
            return NotImplemented

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically to display this file."""
        return str(self)


class Emoji(EmojiBase[objs.EmojiObject], wraps=objs.EmojiObject):
    """Unicode emoji object which behaves like str."""

    def __init__(self, emoji: str) -> None:
        if not is_emoji(emoji):
            emoji = emojize(emoji)
        if not is_emoji(emoji):
            msg = f'Invalid emoji string: {emoji}'
            raise ValueError(msg)
        self.obj_ref = objs.EmojiObject.build(emoji)

    @property
    def name(self) -> str:
        """Return the name of the emoji."""
        return demojize(self.obj_ref.emoji).strip(':')

    def __repr__(self) -> str:
        # we return the unicode emoji to the user for convenience in REPL
        return self.obj_ref.emoji

    def __str__(self) -> str:
        return self.obj_ref.emoji


class CustomEmoji(EmojiBase[objs.CustomEmojiObject], wraps=objs.CustomEmojiObject):
    """Custom emoji object which behaves like str."""

    def __init__(self) -> None:
        msg = 'To create a new custom emoji, go to `Settings` -> `Emoji` in Notion.'
        raise InvalidAPIUsageError(msg)

    @property
    def name(self) -> str:
        """Return the name of this custom emoji."""
        return self.obj_ref.custom_emoji.name

    @property
    def id(self) -> UUID:
        """Return the ID of this custom emoji."""
        return self.obj_ref.custom_emoji.id

    @property
    def url(self) -> str:
        """Return the URL of this custom emoji."""
        return self.obj_ref.custom_emoji.url

    def __repr__(self) -> str:
        return get_repr(self, desc=self.name)

    def __str__(self) -> str:
        return f':{self.name}:'

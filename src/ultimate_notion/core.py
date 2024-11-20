"""Core classes and functions for the Ultimate Notion API."""

from __future__ import annotations

import datetime as dt
from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeVar, cast
from uuid import UUID

from typing_extensions import Self

from ultimate_notion.obj_api import core as obj_core
from ultimate_notion.obj_api import objects as objs

GT = TypeVar('GT', bound=obj_core.GenericObject)  # ToDo: Use new syntax when requires-python >= 3.12

if TYPE_CHECKING:
    from ultimate_notion.session import Session
    from ultimate_notion.user import User


class InvalidAPIUsageError(Exception):
    """Raised when the API is used in an invalid way."""

    def __init__(self, message='This part of the API is not intended to be used in this manner'):
        self.message = message
        super().__init__(self.message)


class ObjRefWrapper(Protocol[GT]):
    """Wrapper for objects that have an obj_ref attribute.

    Note: This allows us to define Mixin classes that require the obj_ref attribute.
    """

    obj_ref: GT


class Wrapper(ObjRefWrapper[GT], ABC):
    """Convert objects from the obj-based API to the high-level API and vice versa."""

    obj_ref: GT

    _obj_api_map: ClassVar[dict[type[GT], type[Wrapper]]] = {}  # type: ignore[misc]

    def __init_subclass__(cls, wraps: type[GT], **kwargs: Any):
        super().__init_subclass__(**kwargs)
        cls._obj_api_map[wraps] = cls

    def __new__(cls, *args, **kwargs) -> Self:
        # Needed for wrap_obj_ref and its call to __new__ to work!
        return super().__new__(cls)

    def __init__(self, *args: Any, **kwargs: Any):
        """Default constructor that also builds `obj_ref`."""
        obj_api_type: type[obj_core.GenericObject] = self._obj_api_map_inv[self.__class__]
        self.obj_ref = obj_api_type.build(*args, **kwargs)

    @classmethod
    def wrap_obj_ref(cls: type[Self], obj_ref: GT, /) -> Self:
        """Wraps low-level `obj_ref` from Notion API into a high-level (hl) object of Ultimate Notion."""
        hl_cls = cls._obj_api_map[type(obj_ref)]
        # To allow for `Block.wrap_obj_ref` to work call a specific 'wrap_obj_ref' if it exists,
        # e.g. `RichText.wrap_obj_ref` we need to break a potential recursion in the MRO.
        if cls.wrap_obj_ref.__func__ is hl_cls.wrap_obj_ref.__func__:  # type: ignore[attr-defined]
            # ToDo: remove type ignore when https://github.com/python/mypy/issues/14123 is fixed
            # break recursion
            hl_obj = hl_cls.__new__(hl_cls)
            hl_obj.obj_ref = obj_ref
            return cast(Self, hl_obj)
        else:
            return cast(Self, hl_cls.wrap_obj_ref(obj_ref))

    @property
    def _obj_api_map_inv(self) -> dict[type[Wrapper], type[GT]]:
        return {v: k for k, v in self._obj_api_map.items()}


NO = TypeVar('NO', bound=obj_core.NotionObject)  # ToDo: Use new syntax when requires-python >= 3.12


class NotionObject(Wrapper[NO], ABC, wraps=obj_core.NotionObject):
    """A top-level Notion API resource."""

    @property
    def id(self) -> UUID | str:
        """Return the ID of the block."""
        return self.obj_ref.id

    @property
    def in_notion(self) -> bool:
        """Return whether the block was created in Notion."""
        return self.obj_ref.id is not None


NE = TypeVar('NE', bound=obj_core.NotionEntity)  # ToDo: Use new syntax when requires-python >= 3.12


class NotionEntity(NotionObject[NE], ABC, wraps=obj_core.NotionEntity):
    def __eq__(self, other: object) -> bool:
        if other is None:
            return False
        elif not isinstance(other, NotionEntity):
            msg = f'Cannot compare {self.__class__.__name__} with {type(other).__name__}'
            raise RuntimeError(msg)
        else:
            return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def id(self) -> UUID:
        """Return the ID of the entity."""
        return self.obj_ref.id

    @property
    def created_time(self) -> dt.datetime:
        """Return the time when the block was created."""
        return self.obj_ref.created_time

    @property
    def created_by(self) -> User:
        """Return the user who created the block."""
        session = get_active_session()
        return session.get_user(self.obj_ref.created_by.id)

    @property
    def last_edited_time(self) -> dt.datetime:
        """Return the time when the block was last edited."""
        return self.obj_ref.last_edited_time

    @property
    def parent(self) -> NotionEntity | None:
        """Return the parent Notion entity or None if the workspace is the parent."""
        session = get_active_session()
        parent = self.obj_ref.parent

        match parent:
            case objs.WorkspaceRef():
                return None
            case objs.PageRef(page_id=page_id):
                return session.get_page(page_ref=page_id)
            case objs.DatabaseRef(database_id=database_id):
                return session.get_db(db_ref=database_id)
            case objs.BlockRef(block_id=block_id):
                return session.get_block(block_ref=block_id)
            case _:
                msg = f'Unknown parent reference {type(parent)}'
                raise RuntimeError(msg)

    @property
    def ancestors(self) -> tuple[NotionEntity, ...]:
        """Return all ancestors from the workspace to the actual record (excluding)."""
        match parent := self.parent:
            case None:
                return ()
            case _:
                return (*parent.ancestors, parent)

    @property
    def is_page(self) -> bool:
        """Return whether the object is a page."""
        return False

    @property
    def is_db(self) -> bool:
        """Return whether the object is a database."""
        return False


def get_active_session() -> Session:
    """Return the current active session or raise an exception.

    Avoids cyclic imports when used within the package itself.
    For internal use mostly.
    """
    from ultimate_notion.session import Session  # noqa: PLC0415

    return Session.get_active()


def get_url(object_id: UUID | str) -> str:
    """Return the URL for the object with the given id."""
    object_id = object_id if isinstance(object_id, UUID) else UUID(object_id)
    return f'https://notion.so/{object_id.hex}'


def get_repr(obj: Any, /, *, name: Any = None, desc: Any = None) -> str:
    """Default representation, i.e. `repr(...)`, used by us for consistency."""
    type_str = str(name) if name is not None else obj.__class__.__name__
    desc_str = str(desc) if desc is not None else str(obj)
    return f"<{type_str}: '{desc_str}' at {hex(id(obj))}>"

"""Core classes and functions for the Ultimate Notion API."""

from __future__ import annotations

import datetime as dt
import logging
from abc import ABC
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Final, Generic, Literal, TypeAlias, cast
from uuid import UUID

from notion_client.errors import APIResponseError
from typing_extensions import Self, TypeVar

from ultimate_notion.obj_api import core as obj_core
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.core import raise_unset

_logger = logging.getLogger(__name__)

# ToDo: Use new syntax when requires-python >= 3.12
GT_co = TypeVar('GT_co', bound=obj_core.GenericObject, default=obj_core.GenericObject, covariant=True)

if TYPE_CHECKING:
    from pydantic_core import SchemaSerializer

    from ultimate_notion.session import Session
    from ultimate_notion.user import User


class Wrapper(Generic[GT_co], ABC):
    """Convert objects from the obj-based API to the high-level API and vice versa."""

    _obj_ref: GT_co

    _obj_api_map: ClassVar[dict[type[GT_co], type[Wrapper]]] = {}  # type: ignore[misc]

    def __init_subclass__(cls, wraps: type[GT_co], **kwargs: Any):
        super().__init_subclass__(**kwargs)
        cls._obj_api_map[wraps] = cls

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        # Needed for wrap_obj_ref and its call to __new__ to work!
        return super().__new__(cls)

    def __init__(self, *args: Any, **kwargs: Any):
        """Default constructor that also builds `obj_ref`."""
        obj_api_type: type[GT_co] = self._obj_api_map_inv[self.__class__]
        self._obj_ref = obj_api_type.build(*args, **kwargs)

    def __pydantic_serializer__(self) -> SchemaSerializer:  # noqa: PLW3201
        """Return the Pydantic serializers for this object."""
        # This is used only when creating a pydantic model from a schema.
        return self._obj_ref.__pydantic_serializer__

    @property
    def obj_ref(self) -> GT_co:
        """Return the low-level Notion-API object reference.

        This is just the answer of the Notion API as a Pydantic model.
        """
        return self._obj_ref

    @obj_ref.setter
    def obj_ref(self, value: GT_co) -> None:  # type: ignore[misc] # breaking covariance
        """Set the low-level Notion-API object reference."""
        self._obj_ref = value

    @classmethod
    def wrap_obj_ref(cls: type[Self], obj_ref: GT_co, /) -> Self:  # type: ignore[misc] # breaking covariance
        """Wraps low-level `obj_ref` from Notion API into a high-level (hl) object of Ultimate Notion."""
        hl_cls = cls._obj_api_map[type(obj_ref)]
        # To allow for `Block.wrap_obj_ref` to work call a specific 'wrap_obj_ref' if it exists,
        # e.g. `RichText.wrap_obj_ref` we need to break a potential recursion in the MRO.
        if cls.wrap_obj_ref.__func__ is hl_cls.wrap_obj_ref.__func__:  # type: ignore[attr-defined]
            # ToDo: remove type ignore when https://github.com/python/mypy/issues/14123 is fixed
            # break recursion
            hl_obj = hl_cls.__new__(hl_cls)
            hl_obj._obj_ref = obj_ref
            return cast(Self, hl_obj)
        else:
            return cast(Self, hl_cls.wrap_obj_ref(obj_ref))

    @property
    def _obj_api_map_inv(self) -> dict[type[Wrapper], type[GT_co]]:
        return {v: k for k, v in self._obj_api_map.items()}


# ToDo: Use new syntax when requires-python >= 3.12
NO_co = TypeVar('NO_co', bound=obj_core.NotionObject, default=obj_core.NotionObject, covariant=True)


class NotionObject(Wrapper[NO_co], ABC, wraps=obj_core.NotionObject):
    """A top-level Notion API resource."""

    @property
    def id(self) -> UUID | str:
        """Return the ID of the block."""
        return raise_unset(self.obj_ref.id)

    @property
    def in_notion(self) -> bool:
        """Return whether the block was created in Notion."""
        return self.obj_ref.id != obj_core.Unset


# This acts as a simple but type-safe sentinel value, which allows narrowing by the type checker with 'is' checks.
class _Workspace(Enum):
    ROOT = 'workspace_root'


Workspace: Final = _Workspace.ROOT
"""This represents the actual root workspace in Notion."""
WorkspaceType: TypeAlias = Literal[_Workspace.ROOT]
"""This represents the type of the root workspace in Notion for type hinting."""

# ToDo: Use new syntax when requires-python >= 3.12
NE_co = TypeVar('NE_co', bound=obj_core.NotionEntity, default=obj_core.NotionEntity, covariant=True)


class NotionEntity(NotionObject[NE_co], ABC, wraps=obj_core.NotionEntity):
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
        return raise_unset(self.obj_ref.id)

    @property
    def created_time(self) -> dt.datetime:
        """Return the time when the block was created."""
        return raise_unset(self.obj_ref.created_time)

    @property
    def created_by(self) -> User:
        """Return the user who created the block."""
        session = get_active_session()
        created_by = raise_unset(self.obj_ref.created_by)
        return session.get_user(raise_unset(created_by.id), raise_on_unknown=False)

    @property
    def last_edited_time(self) -> dt.datetime:
        """Return the time when the block was last edited."""
        return raise_unset(self.obj_ref.last_edited_time)

    @property
    def parent(self) -> NotionEntity | WorkspaceType | None:
        """Return the parent Notion entity, Workspace if the workspace is the parent, or None if not accessible."""
        session = get_active_session()
        parent = raise_unset(self.obj_ref.parent)

        match parent:
            case objs.WorkspaceRef():
                return Workspace
            case objs.PageRef(page_id=page_id):
                try:
                    return session.get_page(page_ref=page_id)
                except APIResponseError as e:
                    msg = f'Error retrieving page with id `{page_id}`: {e}'
                    _logger.warning(msg)
                    return None
            case objs.DatabaseRef(database_id=database_id):
                try:
                    return session.get_db(db_ref=database_id)
                except APIResponseError as e:
                    msg = f'Error retrieving database with id `{database_id}`: {e}'
                    _logger.warning(msg)
                    return None
            case objs.BlockRef(block_id=block_id):
                return session.get_block(block_ref=block_id)
            case _:
                msg = f'Unknown parent reference {type(parent)}'
                raise RuntimeError(msg)

    @property
    def ancestors(self) -> tuple[NotionEntity, ...]:
        """Return all ancestors from the workspace to the actual record (excluding)."""
        if (parent := self.parent) is None or parent is Workspace:
            return ()
        else:
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

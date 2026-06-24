"""Core classes and functions for the Ultimate Notion API."""

from __future__ import annotations

import datetime as dt
import logging
from abc import ABC
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Final, Generic, Literal, TypeAlias
from uuid import UUID

from typing_extensions import Self, TypeIs, TypeVar

from ultimate_notion.errors import UnknownDatabaseError, UnknownPageError, UnsetError
from ultimate_notion.obj_api import core as obj_core
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.core import is_unset

_logger = logging.getLogger(__name__)

# ToDo: Use new syntax when requires-python >= 3.12
GT_co = TypeVar('GT_co', bound=obj_core.GenericObject, default=obj_core.GenericObject, covariant=True)

if TYPE_CHECKING:
    from pydantic_core import SchemaSerializer

    from ultimate_notion.database import Database
    from ultimate_notion.page import Page
    from ultimate_notion.session import Session
    from ultimate_notion.user import User


class Wrapper(Generic[GT_co], ABC):
    """Convert objects from the obj-based API to the high-level API and vice versa."""

    _obj_ref: GT_co | None = None
    """Low-level object reference, ``None`` until built by a constructor or `wrap_obj_ref`."""

    _obj_api_map: ClassVar[dict[type[obj_core.GenericObject], type[Wrapper]]] = {}

    def __init_subclass__(cls, wraps: type[obj_core.GenericObject], **kwargs: Any):
        super().__init_subclass__(**kwargs)
        cls._obj_api_map[wraps] = cls

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        # Needed for wrap_obj_ref and its call to __new__ to work!
        return super().__new__(cls)

    def __init__(self: Wrapper[obj_core.GenericObject], *args: Any, **kwargs: Any):
        """Default constructor that also builds `obj_ref`."""
        obj_api_type = self._obj_api_map_inv[self.__class__]
        self._obj_ref = obj_api_type.build(*args, **kwargs)

    def __pydantic_serializer__(self) -> SchemaSerializer:  # noqa: PLW3201
        """Return the Pydantic serializers for this object."""
        # This is used only when creating a pydantic model from a schema.
        return self.obj_ref.__pydantic_serializer__

    @property
    def obj_ref(self) -> GT_co:
        """Return the low-level Notion-API object reference.

        This is just the answer of the Notion API as a Pydantic model.
        """
        if self._obj_ref is None:
            msg = f'The low-level object reference of {type(self).__name__} is not yet initialized.'
            raise UnsetError(msg)
        return self._obj_ref

    @obj_ref.setter
    def obj_ref(self: Wrapper[obj_core.GenericObject], value: obj_core.GenericObject) -> None:
        """Set the low-level Notion-API object reference.

        Both `self` and `value` are typed against `GenericObject` (the upper bound of the covariant
        `GT_co`) rather than `GT_co` itself: a covariant type variable may not appear in an input
        position. Viewing `self` as `Wrapper[GenericObject]` is sound precisely because `Wrapper` is
        covariant, and it makes the assignment to `_obj_ref` type-check without breaking covariance.
        The getter still narrows the return type to `GT_co`.
        """
        self._obj_ref = value

    @classmethod
    def wrap_obj_ref(cls: type[Self], obj_ref: obj_core.GenericObject, /) -> Self:
        """Wraps low-level `obj_ref` from Notion API into a high-level (hl) object of Ultimate Notion.

        `obj_ref` is typed against `GenericObject` (the upper bound of the covariant `GT_co`) rather
        than `GT_co` itself, since a covariant type variable may not appear in an input position. The
        concrete high-level class is resolved at runtime from the registry keyed on `type(obj_ref)`.
        """
        hl_cls = cls._obj_api_map[type(obj_ref)]
        # Resolving `obj_ref` may yield a more specific high-level class than `cls`, e.g. calling
        # `Block.wrap_obj_ref` on a paragraph object resolves `hl_cls` to `Paragraph`. In that case we
        # hand off to that class' `wrap_obj_ref` so its specialised wrapping (e.g. children handling) runs.
        # Once `cls` already is the resolved class we build the object directly to break the recursion.
        if cls is hl_cls:
            hl_obj = hl_cls.__new__(hl_cls)
            hl_obj._obj_ref = obj_ref
            hl_obj._finalize_wrap()
        else:
            hl_obj = hl_cls.wrap_obj_ref(obj_ref)
        # `cls is hl_cls` makes `hl_obj` an instance of `cls`, while the recursive branch resolves a
        # more specific subclass of `cls`; either way the guard narrows `hl_obj` to `Self` for mypy.
        if not isinstance(hl_obj, cls):
            msg = f'Resolved high-level class `{type(hl_obj).__name__}` is not a `{cls.__name__}`.'
            raise TypeError(msg)
        return hl_obj

    def _finalize_wrap(self) -> None:
        """Run subclass-specific initialisation after `wrap_obj_ref` has set `_obj_ref`.

        Subclasses override this to derive state from `obj_ref` (e.g. an attribute name or child
        blocks). It is an instance method rather than a parameter of `wrap_obj_ref` so that it does
        not take the covariant type variable in an input position, which would break covariance.
        """

    @property
    def _obj_api_map_inv(self) -> dict[type[Wrapper], type[obj_core.GenericObject]]:
        return {v: k for k, v in self._obj_api_map.items()}


# ToDo: Use new syntax when requires-python >= 3.12
NO_co = TypeVar('NO_co', bound=obj_core.NotionObject, default=obj_core.NotionObject, covariant=True)


class NotionObject(Wrapper[NO_co], ABC, wraps=obj_core.NotionObject):
    """A top-level Notion API resource."""

    @property
    def id(self) -> UUID | str:
        """Return the ID of the block."""
        if is_unset(id_ := self.obj_ref.id):
            raise UnsetError()
        return id_

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


def resolve_ref(obj_ref: obj_core.NotionEntity) -> NotionEntity | WorkspaceType | None:
    """Resolve a low-level NotionEntity reference to a high-level NotionEntity object.

    Returns the parent Notion entity, Workspace if the workspace is the parent, or None if not accessible.
    """
    session = get_active_session()
    if is_unset(parent := obj_ref.parent):
        raise UnsetError()

    match parent:
        case objs.WorkspaceRef():
            return Workspace
        case objs.PageRef(page_id=page_id):
            try:
                return session.get_page(page_ref=page_id)
            except UnknownPageError as e:
                msg = f'No access to parent page with id `{page_id}`: {e}'
                _logger.info(msg)
                return None
        case objs.DatabaseRef(database_id=database_id):
            try:
                return session.get_db(db_ref=database_id)
            except UnknownDatabaseError as e:
                msg = f'No access to parent database with id `{database_id}`: {e}'
                _logger.info(msg)
                return None
        case objs.BlockRef(block_id=block_id):
            return session.get_block(block_ref=block_id)
        case _:
            msg = f'Unknown parent reference {type(parent)}'
            raise RuntimeError(msg)


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
        if is_unset(id_ := self.obj_ref.id):
            raise UnsetError()
        return id_

    @property
    def created_time(self) -> dt.datetime:
        """Return the time when the block was created."""
        if is_unset(created_time := self.obj_ref.created_time):
            raise UnsetError()
        return created_time

    @property
    def created_by(self) -> User:
        """Return the user who created the block."""
        session = get_active_session()
        if is_unset(created_by := self.obj_ref.created_by):
            raise UnsetError()
        if is_unset(created_by_id := created_by.id):
            raise UnsetError()
        return session.get_user(created_by_id, raise_on_unknown=False)

    @property
    def last_edited_time(self) -> dt.datetime:
        """Return the time when the block was last edited."""
        if is_unset(last_edited_time := self.obj_ref.last_edited_time):
            raise UnsetError()
        return last_edited_time

    @property
    def parent(self) -> NotionEntity | WorkspaceType | None:
        """Return the parent Notion entity, Workspace if the workspace is the parent, or None if not accessible."""
        return resolve_ref(self.obj_ref)

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


def is_db(obj: NotionEntity | None) -> TypeIs[Database]:
    """Return whether the object is a database as type guard."""
    return obj is not None and obj.is_db


def is_page(obj: NotionEntity | None) -> TypeIs[Page]:
    """Return whether the object is a page as type guard."""
    return obj is not None and obj.is_page

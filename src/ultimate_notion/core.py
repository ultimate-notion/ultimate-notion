"""Core classes and functions for the Ultimate Notion API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeVar, cast
from uuid import UUID

from typing_extensions import Self

from ultimate_notion.obj_api import core as obj_core

GT = TypeVar('GT', bound=obj_core.GenericObject)  # ToDo: Use new syntax when requires-python >= 3.12

if TYPE_CHECKING:
    from ultimate_notion.session import Session


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


class Wrapper(ObjRefWrapper[GT]):
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

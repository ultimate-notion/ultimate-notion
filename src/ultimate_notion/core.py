"""Core classes and functions for the Ultimate Notion API."""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, TypeVar, cast

from typing_extensions import Self

from ultimate_notion.obj_api.core import GenericObject

GT = TypeVar('GT', bound=GenericObject)  # ToDo: Use new syntax when requires-python >= 3.12


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
        obj_api_type: type[GenericObject] = self._obj_api_map_inv[self.__class__]
        self.obj_ref = obj_api_type.build(*args, **kwargs)

    @classmethod
    def wrap_obj_ref(cls: type[Self], obj_ref: GT, /) -> Self:
        """Wraps low-level `obj_ref` from Notion API into a high-level (hl) object of Ultimate Notion."""
        hl_cls = cls._obj_api_map[type(obj_ref)]
        hl_obj = hl_cls.__new__(hl_cls)
        hl_obj.obj_ref = obj_ref
        return cast(Self, hl_obj)

    @property
    def _obj_api_map_inv(self) -> dict[type[Wrapper], type[GT]]:
        return {v: k for k, v in self._obj_api_map.items()}

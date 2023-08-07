from __future__ import annotations

from typing import ClassVar, Any, TYPE_CHECKING
from abc import abstractmethod

import ultimate_notion.obj_api.props as obj_props

if TYPE_CHECKING:
    from ultimate_notion.schema import PropertyType


# Todo: Move the functionality from the PyDantic types in here


class PropertyValue:
    """Base class for Notion property values.

    Used to map high-level objects to low-level Notion-API objects
    """

    obj_ref: obj_props.PropertyValue
    _obj_api_map: ClassVar[dict[type[obj_props.PropertyValue], type[PropertyValue]]] = {}
    _type_value_map: ClassVar[dict[str, type[PropertyValue]]] = {}
    _has_compose: ClassVar[dict[type[obj_props.PropertyValue], bool]] = {}

    def __new__(cls, *args, **kwargs) -> PropertyValue:
        # Needed for wrap_obj_ref and its call to __new__ to work!
        return super().__new__(cls)

    def __init_subclass__(cls, type: type[obj_props.PropertyValue], **kwargs: Any):  # noqa: A002
        super().__init_subclass__(**kwargs)
        cls._obj_api_map[type] = cls
        cls._has_compose[type] = hasattr(type, '__compose__')
        cls._type_value_map[type.type] = cls

    @classmethod
    def wrap_obj_ref(cls, obj_ref: obj_props.PropertyValue) -> PropertyValue:
        prop_type_cls = cls._obj_api_map[type(obj_ref)]
        prop_type = prop_type_cls.__new__(prop_type_cls)
        prop_type.obj_ref = obj_ref
        return prop_type

    @property
    def _obj_api_map_inv(self) -> dict[type[PropertyValue], type[obj_props.PropertyValue]]:
        return {v: k for k, v in self._obj_api_map.items()}

    def __init__(self, *args, **kwargs):
        obj_api_type = self._obj_api_map_inv[self.__class__]
        if hasattr(obj_api_type, "__compose__"):
            self.obj_ref = obj_api_type.__compose__(*args, **kwargs)
        else:
            self.obj_ref = obj_api_type(*args, **kwargs)

    def __eq__(self, other: PropertyValue):
        return self.obj_ref.type == other.obj_ref.type and self.obj_ref() == self.obj_ref()

    @classmethod
    def _get_value_from_type(cls, type: type[PropertyType]) -> type[PropertyValue]:
        """Retrieve the corresponding property value to a type defined in the schema"""
        return cls._type_value_map[type.obj_ref.type]

    # ToDo: Make this abstract and implement in every subclass
    @property
    # @abstractmethod
    def value(self) -> Any:
        return self.obj_ref.Value


class Title(PropertyValue, type=obj_props.Title):
    """Title property value"""


class Text(PropertyValue, type=obj_props.RichText):
    """Rich text property value"""


class Number(PropertyValue, type=obj_props.Number):
    """Simple number property value"""


class Checkbox(PropertyValue, type=obj_props.Checkbox):
    """Simple checkbox type; represented as a boolean."""


class Date(PropertyValue, type=obj_props.Date):
    """Date(-time) property value"""


class Status(PropertyValue, type=obj_props.Status):
    """Status property value"""


class SingleSelect(PropertyValue, type=obj_props.Select):
    """Single select property value"""


class MultiSelect(PropertyValue, type=obj_props.MultiSelect):
    """Notion multi-select type."""


class People(PropertyValue, type=obj_props.People):
    """Notion people type."""


class URL(PropertyValue, type=obj_props.URL):
    """Notion URL type."""


class Email(PropertyValue, type=obj_props.Email):
    """Notion email type."""


class PhoneNumber(PropertyValue, type=obj_props.PhoneNumber):
    """Notion phone type."""


class Files(PropertyValue, type=obj_props.Files):
    """Notion files type."""


class Formula(PropertyValue, type=obj_props.Formula):
    """A Notion formula property value."""


class Relation(PropertyValue, type=obj_props.Relation):
    """A Notion relation property value."""


class Rollup(PropertyValue, type=obj_props.Rollup):
    """A Notion rollup property value."""


class CreatedTime(PropertyValue, type=obj_props.CreatedTime):
    """A Notion created-time property value."""


class CreatedBy(PropertyValue, type=obj_props.CreatedBy):
    """A Notion created-by property value."""


class LastEditedTime(PropertyValue, type=obj_props.LastEditedTime):
    """A Notion last-edited-time property value."""


class LastEditedBy(PropertyValue, type=obj_props.LastEditedBy):
    """A Notion last-edited-by property value."""

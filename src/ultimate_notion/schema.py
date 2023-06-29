"""Functionality around defining a database schema"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from notional import schema
from notional.schema import NumberFormat

from ultimate_notion.utils import SList


class SchemaError(Exception):
    """Raised when there are issues with the schema of a database."""

    def __init__(self, message):
        """Initialize the `NotionSessionError` with a supplied message."""
        super().__init__(message)


class PageSchema:
    # ToDo: Raise excpetion if any of these methods is overwritten!

    @classmethod
    def to_dict(cls) -> dict[str, PropertyType]:
        return {prop.name: prop.type for prop in cls.__dict__.values() if isinstance(prop, Property)}

    @classmethod
    def get_title_property_name(cls):
        return SList(col for col, val in cls.to_dict().items() if isinstance(val, Title)).item()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PageSchema):
            return NotImplemented
        return self.to_dict() == other.to_dict()


class PropertyType:
    """Base class for Notion property objects.

    Used to map our objects to Notional objects for easier usage
    """

    obj_ref: schema.PropertyObject

    _notional_type_map: ClassVar[dict[type[schema.PropertyObject], type[PropertyType]]] = {}
    _has_compose: ClassVar[dict[type[schema.PropertyObject], bool]] = {}

    @property
    def _notional_type_map_inv(self) -> dict[type[PropertyType], type[schema.PropertyObject]]:
        return {v: k for k, v in self._notional_type_map.items()}

    def __init_subclass__(cls, type: type[schema.PropertyObject], **kwargs: Any):  # noqa: A002
        super().__init_subclass__(**kwargs)
        cls._notional_type_map[type] = cls
        cls._has_compose[type] = hasattr(type, '__compose__')

    @classmethod
    def wrap_obj_ref(cls, obj_ref: schema.PropertyObject) -> PropertyType:
        return cls._notional_type_map[type(obj_ref)](obj_ref)

    def __init__(self, *args, **kwargs):
        # check if we just need to wrap, in case `wrap_obj_ref` was called
        if len(args) == 1 and isinstance(args[0], schema.PropertyObject) and not kwargs:
            self.obj_ref = args[0]
            return

        notional_type = self._notional_type_map_inv[self.__class__]
        if self._has_compose[notional_type] and not kwargs:
            self.obj_ref = notional_type[args]
        elif not self._has_compose[notional_type] and not args:
            self.obj_ref = notional_type(**kwargs)
        else:
            msg = 'Use kwargs for composable types and args otherwise'
            raise RuntimeError(msg)

    def __eq__(self, other):
        return self.obj_ref == other.obj_ref


@dataclass
class Property:
    """Property for defining a Notion database schema"""

    name: str
    type: PropertyType  # noqa: A003


class Title(PropertyType, type=schema.Title):
    """Mandatory Title property"""


class Text(PropertyType, type=schema.RichText):
    """Text property"""


class Number(PropertyType, type=schema.Number):
    """Mandatory Title property"""

    def __init__(self, number_format: NumberFormat):
        super().__init__(number_format)


class SelectOption(PropertyType, type=schema.SelectOption):
    """Option for select & multi-select property"""


class SingleSelect(PropertyType, type=schema.Select):
    """Single selection property"""


class MultiSelect(PropertyType, type=schema.MultiSelect):
    """Multi selection property"""


class Status(PropertyType, type=schema.Status):
    """Status property"""


class Date(PropertyType, type=schema.Date):
    """Date property"""


class People(PropertyType, type=schema.People):
    """People property"""


class Files(PropertyType, type=schema.Files):
    """Files property"""


class Checkbox(PropertyType, type=schema.Checkbox):
    """Checkbox property"""


class Email(PropertyType, type=schema.Email):
    """E-Mail property"""


class URL(PropertyType, type=schema.URL):
    """URL property"""


class Formula(PropertyType, type=schema.Formula):
    """Formula Property"""


class Relation(PropertyType, type=schema.Relation):
    """Defines the relation configuration for a database property."""

    # ToDo: Have constructor for one-way/two-way relation


class Rollup(PropertyType, type=schema.Rollup):
    """Defines the rollup configuration for a database property."""

    # ToDo: Neeeds a constructor?


class CreatedTime(PropertyType, type=schema.CreatedTime):
    """Defines the created-time configuration for a database property."""


class CreatedBy(PropertyType, type=schema.CreatedBy):
    """Defines the created-by configuration for a database property."""


class LastEditedBy(PropertyType, type=schema.LastEditedBy):
    """Defines the last-edited-by configuration for a database property."""


class LastEditedTime(PropertyType, type=schema.LastEditedTime):
    """Defines the last-edited-time configuration for a database property."""

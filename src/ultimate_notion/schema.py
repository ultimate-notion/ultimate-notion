"""Functionality around defining a database schema"""
from __future__ import annotations

import inspect
import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import ultimate_notion.obj_api.schema as obj_schema
from ultimate_notion.obj_api.schema import NumberFormat
from ultimate_notion.utils import SList

if TYPE_CHECKING:
    from ultimate_notion.database import Database


class SchemaError(Exception):
    """Raised when there are issues with the schema of a database."""

    def __init__(self, message):
        """Initialize the `NotionSessionError` with a supplied message."""
        super().__init__(message)


class PageSchema:
    _database: Database | None = None
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

    Used to map high-level objects to low-level Notion-API objects
    """

    obj_ref: obj_schema.PropertyObject

    _obj_api_map: ClassVar[dict[type[obj_schema.PropertyObject], type[PropertyType]]] = {}
    # _is_nested: ClassVar[dict[type[obj_schema.PropertyObject], bool]] = {}
    _has_compose: ClassVar[dict[type[obj_schema.PropertyObject], bool]] = {}

    def __new__(cls, *args, **kwargs) -> PropertyType:
        # Needed for wrap_obj_ref and its call to __new__ to work!
        return super().__new__(cls)

    def __init_subclass__(cls, type: type[obj_schema.PropertyObject], **kwargs: Any):  # noqa: A002
        super().__init_subclass__(**kwargs)
        cls._obj_api_map[type] = cls
        cls._has_compose[type] = hasattr(type, '__compose__')

    @property
    def _obj_api_map_inv(self) -> dict[type[PropertyType], type[obj_schema.PropertyObject]]:
        return {v: k for k, v in self._obj_api_map.items()}

    @classmethod
    def wrap_obj_ref(cls, obj_ref: obj_schema.PropertyObject) -> PropertyType:
        prop_type_cls = cls._obj_api_map[type(obj_ref)]
        prop_type = prop_type_cls.__new__(prop_type_cls)
        prop_type.obj_ref = obj_ref
        return prop_type

    @staticmethod
    def _unwrap_obj_api(props: PropertyType | list[PropertyType]):
        if not isinstance(props, list):
            props = [props]
        return [prop.obj_ref if hasattr(prop, 'obj_ref') else prop for prop in props]

    def __init__(self, *args, **kwargs):
        # dispatch to __compose__ or __init__ if it has _NestedData or not, respectively
        obj_api_type = self._obj_api_map_inv[self.__class__]
        if self._has_compose[obj_api_type] and len(args) == 1 and not kwargs:
            params = self._unwrap_obj_api(args[0])
            self.obj_ref = obj_api_type[params]
        elif not self._has_compose[obj_api_type] and not args:
            self.obj_ref = obj_api_type(**kwargs)
        else:
            msg = 'Use args for types with nested data and kwargs otherwise'
            raise RuntimeError(msg)

    def __eq__(self, other):
        return self.obj_ref == other.obj_ref


def resolve_schema(schema_name: str) -> PageSchema:
    if ":" in schema_name:
        module_name, class_name = schema_name.split(":")  # Assuming format "module_name:ClassName"
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
    else:
        cls = globals().get(schema_name)

    if inspect.isclass(cls) and issubclass(cls, PageSchema):
        return cls
    else:
        raise TypeError(f"Schema name '{schema_name}' does not refer to a `PageSchema` subclass.")


@dataclass
class Property:
    """Property for defining a Notion database schema"""

    name: str
    type: PropertyType  # noqa: A003


class Title(PropertyType, type=obj_schema.Title):
    """Mandatory Title property"""


class Text(PropertyType, type=obj_schema.RichText):
    """Text property"""


class Number(PropertyType, type=obj_schema.Number):
    """Mandatory Title property"""

    def __init__(self, number_format: NumberFormat):
        super().__init__(number_format)


class SelectOption(PropertyType, type=obj_schema.SelectOption):
    """Option for select & multi-select property"""


class SingleSelect(PropertyType, type=obj_schema.Select):
    """Single selection property"""


class MultiSelect(PropertyType, type=obj_schema.MultiSelect):
    """Multi selection property"""


class Status(PropertyType, type=obj_schema.Status):
    """Status property"""


class Date(PropertyType, type=obj_schema.Date):
    """Date property"""


class People(PropertyType, type=obj_schema.People):
    """People property"""


class Files(PropertyType, type=obj_schema.Files):
    """Files property"""


class Checkbox(PropertyType, type=obj_schema.Checkbox):
    """Checkbox property"""


class Email(PropertyType, type=obj_schema.Email):
    """E-Mail property"""


class URL(PropertyType, type=obj_schema.URL):
    """URL property"""


class Formula(PropertyType, type=obj_schema.Formula):
    """Formula Property"""


class Relation(PropertyType, type=obj_schema.Relation):
    _schema: str | None = None
    _backref: str | None = None

    def __init__(self, schema: str | PageSchema, two_way: bool = False, related_prop: str | None = None):
        self._schema = schema
        self._backref = backref

    def bind_db(self):
        """Actual Notion object obj_ref is constructed"""
        schema = resolve_schema(self._schema)
        if self._backref:
            super().__init__(schema._database.id)
        else:
            super().__init__(schema._database.id)

    # ToDo: Let the PageSchema object do the late binding! When used in create_db ensure_db or set schema!


class Rollup(PropertyType, type=obj_schema.Rollup):
    """Defines the rollup configuration for a database property."""

    # ToDo: Needs a constructor?


class CreatedTime(PropertyType, type=obj_schema.CreatedTime):
    """Defines the created-time configuration for a database property."""


class CreatedBy(PropertyType, type=obj_schema.CreatedBy):
    """Defines the created-by configuration for a database property."""


class LastEditedBy(PropertyType, type=obj_schema.LastEditedBy):
    """Defines the last-edited-by configuration for a database property."""


class LastEditedTime(PropertyType, type=obj_schema.LastEditedTime):
    """Defines the last-edited-time configuration for a database property."""

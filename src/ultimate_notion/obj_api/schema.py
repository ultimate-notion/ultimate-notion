"""Objects representing a database schema."""
# ToDo: Following line creates a forward reference error in pydantic. Is this fixed in Pydantic 2?
# from __future__ import annotations
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

import pydantic

from ultimate_notion.obj_api.core import GenericObject, TypedObject
from ultimate_notion.obj_api.enums import NumberFormat, Function
from ultimate_notion.obj_api.objects import SelectOption


class VerificationState(str, Enum):
    """Available verification states for pages in wiki databases"""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class PropertyObject(TypedObject):
    """Base class for Notion property objects."""

    id: Optional[str] = None
    name: Optional[str] = None


class Title(PropertyObject, type="title"):
    """Defines the title configuration for a database property."""

    title: Any = {}


class RichText(PropertyObject, type="rich_text"):
    """Defines the rich text configuration for a database property."""

    rich_text: Any = {}


class Number(PropertyObject, type="number"):
    """Defines the number configuration for a database property."""

    class _NestedData(GenericObject):
        format: NumberFormat = NumberFormat.NUMBER

        # leads to better error messages, see
        # https://github.com/pydantic/pydantic/issues/355
        @pydantic.validator("format", pre=True)
        def validate_enum_field(cls, field: str):
            return NumberFormat(field)

    number: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, format):
        """Create a `Number` object with the expected format."""
        return cls(number=cls._NestedData(format=format))


class Select(PropertyObject, type="select"):
    """Defines the select configuration for a database property."""

    class _NestedData(GenericObject):
        options: List[SelectOption] = []

    select: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, options):
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls(select=cls._NestedData(options=options))


class MultiSelect(PropertyObject, type="multi_select"):
    """Defines the multi-select configuration for a database property."""

    class _NestedData(GenericObject):
        options: List[SelectOption] = []

    multi_select: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, options):
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls(multi_select=cls._NestedData(options=options))


class Status(PropertyObject, type="status"):
    """Defines the status configuration for a database property."""

    status: Any = {}


class Date(PropertyObject, type="date"):
    """Defines the date configuration for a database property."""

    date: Any = {}


class People(PropertyObject, type="people"):
    """Defines the people configuration for a database property."""

    people: Any = {}


class Files(PropertyObject, type="files"):
    """Defines the files configuration for a database property."""

    files: Any = {}


class Checkbox(PropertyObject, type="checkbox"):
    """Defines the checkbox configuration for a database property."""

    checkbox: Any = {}


class Email(PropertyObject, type="email"):
    """Defines the email configuration for a database property."""

    email: Any = {}


class URL(PropertyObject, type="url"):
    """Defines the URL configuration for a database property."""

    url: Any = {}


class PhoneNumber(PropertyObject, type="phone_number"):
    """Defines the phone number configuration for a database property."""

    phone_number: Any = {}


class Formula(PropertyObject, type="formula"):
    """Defines the formula configuration for a database property."""

    class _NestedData(GenericObject):
        expression: str = None

    formula: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, expression):
        return cls(formula=cls._NestedData(expression=expression))


class PropertyRelation(TypedObject):
    """Defines common configuration for a property relation."""

    database_id: UUID = None


class SinglePropertyRelation(PropertyRelation, type="single_property"):
    """Defines a one-way relation configuration for a database property."""

    single_property: Any = {}

    @classmethod
    def __compose__(cls, dbref):
        """Create a `single_property` relation using the target database reference.

        `dbref` must be either a string or UUID.
        """

        return Relation(relation=SinglePropertyRelation(database_id=dbref))


class DualPropertyRelation(PropertyRelation, type="dual_property"):
    """Defines a two-way relation configuration for a database property.

    If a two-way relation property X relates to Y then the two-way relation property Y relates to X.
    """

    class _NestedData(GenericObject):
        synced_property_name: Optional[str] = None
        synced_property_id: Optional[str] = None

    dual_property: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, dbref):
        """Create a `dual_property` relation using the target database reference.

        `dbref` must be either a string or UUID.
        """
        return Relation(relation=DualPropertyRelation(database_id=dbref))


class Relation(PropertyObject, type="relation"):
    """Defines the relation configuration for a database property."""

    relation: PropertyRelation = PropertyRelation()


class Rollup(PropertyObject, type="rollup"):
    """Defines the rollup configuration for a database property."""

    class _NestedData(GenericObject):
        function: Function = Function.COUNT

        relation_property_name: Optional[str] = None
        relation_property_id: Optional[str] = None

        rollup_property_name: Optional[str] = None
        rollup_property_id: Optional[str] = None

        # leads to better error messages, see
        # https://github.com/pydantic/pydantic/issues/355
        @pydantic.validator("function", pre=True)
        def validate_enum_field(cls, field: str):
            return Function(field)

    rollup: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, relation, property, function):
        return Rollup(
            rollup=cls._NestedData(function=function, relation_property_name=relation, rollup_property_name=property)
        )


class CreatedTime(PropertyObject, type="created_time"):
    """Defines the created-time configuration for a database property."""

    created_time: Any = {}


class CreatedBy(PropertyObject, type="created_by"):
    """Defines the created-by configuration for a database property."""

    created_by: Any = {}


class LastEditedBy(PropertyObject, type="last_edited_by"):
    """Defines the last-edited-by configuration for a database property."""

    last_edited_by: Any = {}


class LastEditedTime(PropertyObject, type="last_edited_time"):
    """Defines the last-edited-time configuration for a database property."""

    last_edited_time: Any = {}


class UniqueID(PropertyObject, type="unique_id"):
    """Unique ID database property"""

    unique_id: Any = {}


class Verification(PropertyObject, type="verification"):
    """Verfication database property of Wiki databases"""

    verification: Any = {}


class RenameProp(GenericObject):
    """Use to rename a property during a database update"""

    name: str

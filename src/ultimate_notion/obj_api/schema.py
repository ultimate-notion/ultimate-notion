"""Objects representing a database schema."""
# ToDo: Following line creates a forward reference error in pydantic. Is this fixed in Pydantic 2?
# from __future__ import annotations
from typing import Any
from uuid import UUID

import pydantic
from pydantic import Field

from ultimate_notion.obj_api.core import GenericObject, TypedObject
from ultimate_notion.obj_api.enums import Function, NumberFormat
from ultimate_notion.obj_api.objects import SelectOption


class PropertyType(TypedObject):
    """Base class for Notion property objects."""

    id: str | None = None  # noqa: A003
    name: str | None = None


class Title(PropertyType, type='title'):
    """Defines the title configuration for a database property."""

    title: Any = Field(default_factory=dict)


class RichText(PropertyType, type='rich_text'):
    """Defines the rich text configuration for a database property."""

    rich_text: Any = Field(default_factory=dict)


class Number(PropertyType, type='number'):
    """Defines the number configuration for a database property."""

    class _NestedData(GenericObject):
        format: NumberFormat = NumberFormat.NUMBER  # noqa: A003

        # leads to better error messages, see
        # https://github.com/pydantic/pydantic/issues/355
        @pydantic.validator('format', pre=True)
        @classmethod
        def validate_enum_field(cls, field: str):
            return NumberFormat(field)

    number: _NestedData = _NestedData()

    @classmethod
    def build(cls, format):  # noqa: A002
        """Create a `Number` object with the expected format."""
        return cls(number=cls._NestedData(format=format))


class Select(PropertyType, type='select'):
    """Defines the select configuration for a database property."""

    class _NestedData(GenericObject):
        options: list[SelectOption] = Field(default_factory=list)

    select: _NestedData = _NestedData()

    @classmethod
    def build(cls, options):
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls(select=cls._NestedData(options=options))


class MultiSelect(PropertyType, type='multi_select'):
    """Defines the multi-select configuration for a database property."""

    class _NestedData(GenericObject):
        options: list[SelectOption] = Field(default_factory=list)

    multi_select: _NestedData = _NestedData()

    @classmethod
    def build(cls, options):
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls(multi_select=cls._NestedData(options=options))


class Status(PropertyType, type='status'):
    """Defines the status configuration for a database property."""

    status: Any = Field(default_factory=dict)


class Date(PropertyType, type='date'):
    """Defines the date configuration for a database property."""

    date: Any = Field(default_factory=dict)


class People(PropertyType, type='people'):
    """Defines the people configuration for a database property."""

    people: Any = Field(default_factory=dict)


class Files(PropertyType, type='files'):
    """Defines the files configuration for a database property."""

    files: Any = Field(default_factory=dict)


class Checkbox(PropertyType, type='checkbox'):
    """Defines the checkbox configuration for a database property."""

    checkbox: Any = Field(default_factory=dict)


class Email(PropertyType, type='email'):
    """Defines the email configuration for a database property."""

    email: Any = Field(default_factory=dict)


class URL(PropertyType, type='url'):
    """Defines the URL configuration for a database property."""

    url: Any = Field(default_factory=dict)


class PhoneNumber(PropertyType, type='phone_number'):
    """Defines the phone number configuration for a database property."""

    phone_number: Any = Field(default_factory=dict)


class Formula(PropertyType, type='formula'):
    """Defines the formula configuration for a database property."""

    class _NestedData(GenericObject):
        expression: str = None

    formula: _NestedData = _NestedData()

    @classmethod
    def build(cls, expression):
        return cls(formula=cls._NestedData(expression=expression))


class PropertyRelation(TypedObject):
    """Defines common configuration for a property relation."""

    database_id: UUID = None


class SinglePropertyRelation(PropertyRelation, type='single_property'):
    """Defines a one-way relation configuration for a database property."""

    single_property: Any = Field(default_factory=dict)

    @classmethod
    def build(cls, dbref):
        """Create a `single_property` relation using the target database reference.

        `dbref` must be either a string or UUID.
        """

        return Relation(relation=SinglePropertyRelation(database_id=dbref))


class DualPropertyRelation(PropertyRelation, type='dual_property'):
    """Defines a two-way relation configuration for a database property.

    If a two-way relation property X relates to Y then the two-way relation property Y relates to X.
    """

    class _NestedData(GenericObject):
        synced_property_name: str | None = None
        synced_property_id: str | None = None

    dual_property: _NestedData = _NestedData()

    @classmethod
    def build(cls, dbref):
        """Create a `dual_property` relation using the target database reference.

        `dbref` must be either a string or UUID.
        """
        return Relation(relation=DualPropertyRelation(database_id=dbref))


class Relation(PropertyType, type='relation'):
    """Defines the relation configuration for a database property."""

    relation: PropertyRelation = PropertyRelation()


class Rollup(PropertyType, type='rollup'):
    """Defines the rollup configuration for a database property."""

    class _NestedData(GenericObject):
        function: Function = Function.COUNT

        relation_property_name: str | None = None
        relation_property_id: str | None = None

        rollup_property_name: str | None = None
        rollup_property_id: str | None = None

        # leads to better error messages, see
        # https://github.com/pydantic/pydantic/issues/355
        @pydantic.validator('function', pre=True)
        @classmethod
        def validate_enum_field(cls, field: str):
            return Function(field)

    rollup: _NestedData = _NestedData()

    @classmethod
    def build(cls, relation, property, function):  # noqa: A002
        return Rollup(
            rollup=cls._NestedData(function=function, relation_property_name=relation, rollup_property_name=property)
        )


class CreatedTime(PropertyType, type='created_time'):
    """Defines the created-time configuration for a database property."""

    created_time: Any = Field(default_factory=dict)


class CreatedBy(PropertyType, type='created_by'):
    """Defines the created-by configuration for a database property."""

    created_by: Any = Field(default_factory=dict)


class LastEditedBy(PropertyType, type='last_edited_by'):
    """Defines the last-edited-by configuration for a database property."""

    last_edited_by: Any = Field(default_factory=dict)


class LastEditedTime(PropertyType, type='last_edited_time'):
    """Defines the last-edited-time configuration for a database property."""

    last_edited_time: Any = Field(default_factory=dict)


class UniqueID(PropertyType, type='unique_id'):
    """Unique ID database property"""

    unique_id: Any = Field(default_factory=dict)


class Verification(PropertyType, type='verification'):
    """Verfication database property of Wiki databases"""

    verification: Any = Field(default_factory=dict)


class RenameProp(GenericObject):
    """Use to rename a property during a database update"""

    name: str

"""Objects representing a database schema."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field, SerializeAsAny, field_validator

from ultimate_notion.obj_api.core import GenericObject, TypedObject
from ultimate_notion.obj_api.enums import AggFunc, NumberFormat
from ultimate_notion.obj_api.objects import SelectGroup, SelectOption


class PropertyType(TypedObject, polymorphic_base=True):
    """Base class for Notion property objects."""

    id: str | None = None
    name: str | None = None

    @classmethod
    def build(cls):
        """Build the property value from given value, e.g. native Python or nested type.

        In practice, this is like calling __init__ with the corresponding keyword.
        """
        return cls.model_construct()


class Title(PropertyType, type='title'):
    """Defines the title configuration for a database property."""

    title: Any = Field(default_factory=dict)


class RichText(PropertyType, type='rich_text'):
    """Defines the rich text configuration for a database property."""

    rich_text: Any = Field(default_factory=dict)


class Number(PropertyType, type='number'):
    """Defines the number configuration for a database property."""

    class _NestedData(GenericObject):
        format: NumberFormat = NumberFormat.NUMBER

        # leads to better error messages, see
        # https://github.com/pydantic/pydantic/issues/355
        @field_validator('format')
        @classmethod
        def validate_enum_field(cls, field: str):
            return NumberFormat(field)

    number: _NestedData = _NestedData()

    @classmethod
    def build(cls, format):  # noqa: A002
        """Create a `Number` object with the expected format."""
        return cls.model_construct(number=cls._NestedData(format=format))


class Select(PropertyType, type='select'):
    """Defines the select configuration for a database property."""

    class _NestedData(GenericObject):
        options: list[SelectOption] = Field(default_factory=list)

    select: _NestedData = _NestedData()

    @classmethod
    def build(cls, options):
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls.model_construct(select=cls._NestedData(options=options))


class MultiSelect(PropertyType, type='multi_select'):
    """Defines the multi-select configuration for a database property."""

    class _NestedData(GenericObject):
        options: list[SelectOption] = Field(default_factory=list)

    multi_select: _NestedData = _NestedData()

    @classmethod
    def build(cls, options):
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls.model_construct(multi_select=cls._NestedData(options=options))


class Status(PropertyType, type='status'):
    """Defines the status configuration for a database property."""

    class _NestedData(GenericObject):
        options: list[SelectOption] = Field(default_factory=list)
        groups: list[SelectGroup] = Field(default_factory=list)

    status: _NestedData = _NestedData()


class Date(PropertyType, type='date'):
    """Defines the date configuration for a database property."""

    class _NestedData(GenericObject):
        ...

    date: _NestedData = _NestedData()


class People(PropertyType, type='people'):
    """Defines the people configuration for a database property."""

    class _NestedData(GenericObject):
        ...

    people: _NestedData = _NestedData()


class Files(PropertyType, type='files'):
    """Defines the files configuration for a database property."""

    class _NestedData(GenericObject):
        ...

    files: _NestedData = _NestedData()


class Checkbox(PropertyType, type='checkbox'):
    """Defines the checkbox configuration for a database property."""

    class _NestedData(GenericObject):
        ...

    checkbox: _NestedData = _NestedData()


class Email(PropertyType, type='email'):
    """Defines the email configuration for a database property."""

    class _NestedData(GenericObject):
        ...

    email: _NestedData = _NestedData()


class URL(PropertyType, type='url'):
    """Defines the URL configuration for a database property."""

    class _NestedData(GenericObject):
        ...

    url: _NestedData = _NestedData()


class PhoneNumber(PropertyType, type='phone_number'):
    """Defines the phone number configuration for a database property."""

    class _NestedData(GenericObject):
        ...

    phone_number: _NestedData = _NestedData()


class Formula(PropertyType, type='formula'):
    """Defines the formula configuration for a database property."""

    class _NestedData(GenericObject):
        expression: str = None  # type: ignore

    formula: _NestedData = _NestedData()

    @classmethod
    def build(cls, expression):
        return cls.model_construct(formula=cls._NestedData(expression=expression))


class PropertyRelation(TypedObject, polymorphic_base=True):
    """Defines common configuration for a property relation."""

    database_id: UUID = None  # type: ignore


class SinglePropertyRelation(PropertyRelation, type='single_property'):
    """Defines a one-way relation configuration for a database property."""

    single_property: Any = Field(default_factory=dict)

    @classmethod
    def build(cls, dbref):
        """Create a `single_property` relation using the target database reference.

        `dbref` must be either a string or UUID.
        """
        rel = SinglePropertyRelation.model_construct(database_id=dbref)
        return Relation.model_construct(relation=rel)


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
        rel = DualPropertyRelation.model_construct(database_id=dbref)
        return Relation.model_construct(relation=rel)


class Relation(PropertyType, type='relation'):
    """Defines the relation configuration for a database property."""

    relation: SerializeAsAny[PropertyRelation]


class Rollup(PropertyType, type='rollup'):
    """Defines the rollup configuration for a database property."""

    class _NestedData(GenericObject):
        function: AggFunc = AggFunc.COUNT

        relation_property_name: str | None = None
        relation_property_id: str | None = None

        rollup_property_name: str | None = None
        rollup_property_id: str | None = None

        # leads to better error messages, see
        # https://github.com/pydantic/pydantic/issues/355
        @field_validator('function')
        @classmethod
        def validate_enum_field(cls, field: str):
            return AggFunc(field)

    rollup: _NestedData = _NestedData()

    @classmethod
    def build(cls, relation, property, function):  # noqa: A002
        return Rollup.model_construct(
            rollup=cls._NestedData(function=function, relation_property_name=relation, rollup_property_name=property)
        )


class CreatedTime(PropertyType, type='created_time'):
    """Defines the created-time configuration for a database property."""

    class _NestedData(GenericObject):
        ...

    created_time: _NestedData = _NestedData()


class CreatedBy(PropertyType, type='created_by'):
    """Defines the created-by configuration for a database property."""

    class _NestedData(GenericObject):
        ...

    created_by: _NestedData = _NestedData()


class LastEditedBy(PropertyType, type='last_edited_by'):
    """Defines the last-edited-by configuration for a database property."""

    class _NestedData(GenericObject):
        ...

    last_edited_by: _NestedData = _NestedData()


class LastEditedTime(PropertyType, type='last_edited_time'):
    """Defines the last-edited-time configuration for a database property."""

    class _NestedData(GenericObject):
        ...

    last_edited_time: _NestedData = _NestedData()


class UniqueID(PropertyType, type='unique_id'):
    """Unique ID database property."""

    class _NestedData(GenericObject):
        prefix: str | None = None

    unique_id: _NestedData = _NestedData()


class Verification(PropertyType, type='verification'):
    """Verfication database property of Wiki databases."""

    class _NestedData(GenericObject):
        ...

    verification: _NestedData = _NestedData()


class RenameProp(GenericObject):
    """Use to rename a property during a database update."""

    name: str

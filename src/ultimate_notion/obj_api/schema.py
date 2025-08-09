"""Objects representing a database schema."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, SerializeAsAny, field_validator

from ultimate_notion.obj_api.core import GenericObject, TypedObject
from ultimate_notion.obj_api.enums import AggFunc, NumberFormat
from ultimate_notion.obj_api.objects import SelectGroup, SelectOption


class Property(TypedObject, polymorphic_base=True):
    """Base class for Notion property objects."""

    id: str = None  # type: ignore
    name: str = None  # type: ignore


class Title(Property, type='title'):
    """Defines the title configuration for a database property."""

    class TypeData(GenericObject): ...

    title: TypeData = TypeData()


class RichText(Property, type='rich_text'):
    """Defines the rich text configuration for a database property."""

    class TypeData(GenericObject): ...

    rich_text: TypeData = TypeData()


class Number(Property, type='number'):
    """Defines the number configuration for a database property."""

    class TypeData(GenericObject):
        format: NumberFormat = NumberFormat.NUMBER

        # leads to better error messages, see
        # https://github.com/pydantic/pydantic/issues/355
        @field_validator('format')
        @classmethod
        def validate_enum_field(cls, field: str) -> NumberFormat:
            return NumberFormat(field)

    number: TypeData = TypeData()

    @classmethod
    def build(cls, format: NumberFormat) -> Number:  # noqa: A002
        """Create a `Number` object with the expected format."""
        return cls.model_construct(number=cls.TypeData(format=format))


class Select(Property, type='select'):
    """Defines the select configuration for a database property."""

    class TypeData(GenericObject):
        options: list[SelectOption] = Field(default_factory=list)

    select: TypeData = TypeData()

    @classmethod
    def build(cls, options: list[SelectOption]) -> Select:
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls.model_construct(select=cls.TypeData(options=options))


class MultiSelect(Property, type='multi_select'):
    """Defines the multi-select configuration for a database property."""

    class TypeData(GenericObject):
        options: list[SelectOption] = Field(default_factory=list)

    multi_select: TypeData = TypeData()

    @classmethod
    def build(cls, options: list[SelectOption]) -> MultiSelect:
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls.model_construct(multi_select=cls.TypeData(options=options))


class Status(Property, type='status'):
    """Defines the status configuration for a database property."""

    class TypeData(GenericObject):
        options: list[SelectOption] = Field(default_factory=list)
        groups: list[SelectGroup] = Field(default_factory=list)

    status: TypeData = TypeData()


class Date(Property, type='date'):
    """Defines the date configuration for a database property."""

    class TypeData(GenericObject): ...

    date: TypeData = TypeData()


class People(Property, type='people'):
    """Defines the people configuration for a database property."""

    class TypeData(GenericObject): ...

    people: TypeData = TypeData()


class Files(Property, type='files'):
    """Defines the files configuration for a database property."""

    class TypeData(GenericObject): ...

    files: TypeData = TypeData()


class Checkbox(Property, type='checkbox'):
    """Defines the checkbox configuration for a database property."""

    class TypeData(GenericObject): ...

    checkbox: TypeData = TypeData()


class Email(Property, type='email'):
    """Defines the email configuration for a database property."""

    class TypeData(GenericObject): ...

    email: TypeData = TypeData()


class URL(Property, type='url'):
    """Defines the URL configuration for a database property."""

    class TypeData(GenericObject): ...

    url: TypeData = TypeData()


class PhoneNumber(Property, type='phone_number'):
    """Defines the phone number configuration for a database property."""

    class TypeData(GenericObject): ...

    phone_number: TypeData = TypeData()


class Formula(Property, type='formula'):
    """Defines the formula configuration for a database property."""

    class TypeData(GenericObject):
        expression: str = None  # type: ignore

    formula: TypeData = TypeData()

    @classmethod
    def build(cls, formula: str) -> Formula:
        return cls.model_construct(formula=cls.TypeData(expression=formula))


class PropertyRelation(TypedObject, polymorphic_base=True):
    """Defines common configuration for a property relation."""

    database_id: UUID = None  # type: ignore


class SinglePropertyRelation(PropertyRelation, type='single_property'):
    """Defines a one-way relation configuration for a database property."""

    class TypeData(GenericObject): ...

    single_property: TypeData = TypeData()

    @classmethod
    def build(cls, dbref: UUID) -> Relation:
        """Create a `single_property` relation using the target database reference.

        `dbref` must be either a string or UUID.
        """
        rel = SinglePropertyRelation.model_construct(database_id=dbref)
        return Relation.model_construct(relation=rel)


class DualPropertyRelation(PropertyRelation, type='dual_property'):
    """Defines a two-way relation configuration for a database property.

    If a two-way relation property X relates to Y then the two-way relation property Y relates to X.
    """

    class TypeData(GenericObject):
        synced_property_name: str = None  # type: ignore
        synced_property_id: str | None = None

    dual_property: TypeData = TypeData()

    @classmethod
    def build(cls, dbref: UUID) -> Relation:
        """Create a `dual_property` relation using the target database reference.

        `dbref` must be either a string or UUID.
        """
        rel = DualPropertyRelation.model_construct(database_id=dbref)
        return Relation.model_construct(relation=rel)


class Relation(Property, type='relation'):
    """Defines the relation configuration for a database property."""

    relation: SerializeAsAny[PropertyRelation]


class Rollup(Property, type='rollup'):
    """Defines the rollup configuration for a database property."""

    class TypeData(GenericObject):
        function: AggFunc = AggFunc.COUNT_ALL

        relation_property_name: str = None  # type: ignore
        relation_property_id: str | None = None

        rollup_property_name: str = None  # type: ignore
        rollup_property_id: str | None = None

        # leads to better error messages, see
        # https://github.com/pydantic/pydantic/issues/355
        @field_validator('function')
        @classmethod
        def validate_enum_field(cls, field: str) -> AggFunc:
            return AggFunc(field)

    rollup: TypeData = TypeData()

    @classmethod
    def build(cls, relation: str, property: str, function: AggFunc) -> Rollup:  # noqa: A002
        return Rollup.model_construct(
            rollup=cls.TypeData(function=function, relation_property_name=relation, rollup_property_name=property)
        )


class CreatedTime(Property, type='created_time'):
    """Defines the created-time configuration for a database property."""

    class TypeData(GenericObject): ...

    created_time: TypeData = TypeData()


class CreatedBy(Property, type='created_by'):
    """Defines the created-by configuration for a database property."""

    class TypeData(GenericObject): ...

    created_by: TypeData = TypeData()


class LastEditedBy(Property, type='last_edited_by'):
    """Defines the last-edited-by configuration for a database property."""

    class TypeData(GenericObject): ...

    last_edited_by: TypeData = TypeData()


class LastEditedTime(Property, type='last_edited_time'):
    """Defines the last-edited-time configuration for a database property."""

    class TypeData(GenericObject): ...

    last_edited_time: TypeData = TypeData()


class UniqueID(Property, type='unique_id'):
    """Unique ID database property."""

    class TypeData(GenericObject):
        prefix: str | None = None

    unique_id: TypeData = TypeData()


class Verification(Property, type='verification'):
    """Verfication database property of Wiki databases."""

    class TypeData(GenericObject): ...

    verification: TypeData = TypeData()


class Button(Property, type='button'):
    """Button database property."""

    class TypeData(GenericObject): ...

    button: TypeData = TypeData()


class RenameProp(GenericObject):
    """Property to rename a property during a database update."""

    name: str

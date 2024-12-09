"""Objects representing a database schema."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, SerializeAsAny, field_validator

from ultimate_notion.obj_api.core import GenericObject, TypedObject
from ultimate_notion.obj_api.enums import AggFunc, NumberFormat
from ultimate_notion.obj_api.objects import SelectGroup, SelectOption


class PropertyType(TypedObject, polymorphic_base=True):
    """Base class for Notion property objects."""

    id: str | None = None
    name: str | None = None


class Title(PropertyType, type='title'):
    """Defines the title configuration for a database property."""

    class TypeData(GenericObject): ...

    title: TypeData = TypeData()


class RichText(PropertyType, type='rich_text'):
    """Defines the rich text configuration for a database property."""

    class TypeData(GenericObject): ...

    rich_text: TypeData = TypeData()


class Number(PropertyType, type='number'):
    """Defines the number configuration for a database property."""

    class TypeData(GenericObject):
        format: NumberFormat = NumberFormat.NUMBER

        # leads to better error messages, see
        # https://github.com/pydantic/pydantic/issues/355
        @field_validator('format')
        @classmethod
        def validate_enum_field(cls, field: str):
            return NumberFormat(field)

    number: TypeData = TypeData()

    @classmethod
    def build(cls, format):  # noqa: A002
        """Create a `Number` object with the expected format."""
        return cls.model_construct(number=cls.TypeData(format=format))


class Select(PropertyType, type='select'):
    """Defines the select configuration for a database property."""

    class TypeData(GenericObject):
        options: list[SelectOption] = Field(default_factory=list)

    select: TypeData = TypeData()

    @classmethod
    def build(cls, options):
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls.model_construct(select=cls.TypeData(options=options))


class MultiSelect(PropertyType, type='multi_select'):
    """Defines the multi-select configuration for a database property."""

    class TypeData(GenericObject):
        options: list[SelectOption] = Field(default_factory=list)

    multi_select: TypeData = TypeData()

    @classmethod
    def build(cls, options):
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls.model_construct(multi_select=cls.TypeData(options=options))


class Status(PropertyType, type='status'):
    """Defines the status configuration for a database property."""

    class TypeData(GenericObject):
        options: list[SelectOption] = Field(default_factory=list)
        groups: list[SelectGroup] = Field(default_factory=list)

    status: TypeData = TypeData()


class Date(PropertyType, type='date'):
    """Defines the date configuration for a database property."""

    class TypeData(GenericObject): ...

    date: TypeData = TypeData()


class People(PropertyType, type='people'):
    """Defines the people configuration for a database property."""

    class TypeData(GenericObject): ...

    people: TypeData = TypeData()


class Files(PropertyType, type='files'):
    """Defines the files configuration for a database property."""

    class TypeData(GenericObject): ...

    files: TypeData = TypeData()


class Checkbox(PropertyType, type='checkbox'):
    """Defines the checkbox configuration for a database property."""

    class TypeData(GenericObject): ...

    checkbox: TypeData = TypeData()


class Email(PropertyType, type='email'):
    """Defines the email configuration for a database property."""

    class TypeData(GenericObject): ...

    email: TypeData = TypeData()


class URL(PropertyType, type='url'):
    """Defines the URL configuration for a database property."""

    class TypeData(GenericObject): ...

    url: TypeData = TypeData()


class PhoneNumber(PropertyType, type='phone_number'):
    """Defines the phone number configuration for a database property."""

    class TypeData(GenericObject): ...

    phone_number: TypeData = TypeData()


class Formula(PropertyType, type='formula'):
    """Defines the formula configuration for a database property."""

    class TypeData(GenericObject):
        expression: str = None  # type: ignore

    formula: TypeData = TypeData()

    @classmethod
    def build(cls, expression):
        return cls.model_construct(formula=cls.TypeData(expression=expression))


class PropertyRelation(TypedObject, polymorphic_base=True):
    """Defines common configuration for a property relation."""

    database_id: UUID = None  # type: ignore


class SinglePropertyRelation(PropertyRelation, type='single_property'):
    """Defines a one-way relation configuration for a database property."""

    class TypeData(GenericObject): ...

    single_property: TypeData = TypeData()

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

    class TypeData(GenericObject):
        synced_property_name: str = None  # type: ignore
        synced_property_id: str | None = None

    dual_property: TypeData = TypeData()

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
        def validate_enum_field(cls, field: str):
            return AggFunc(field)

    rollup: TypeData = TypeData()

    @classmethod
    def build(cls, relation, property, function):  # noqa: A002
        return Rollup.model_construct(
            rollup=cls.TypeData(function=function, relation_property_name=relation, rollup_property_name=property)
        )


class CreatedTime(PropertyType, type='created_time'):
    """Defines the created-time configuration for a database property."""

    class TypeData(GenericObject): ...

    created_time: TypeData = TypeData()


class CreatedBy(PropertyType, type='created_by'):
    """Defines the created-by configuration for a database property."""

    class TypeData(GenericObject): ...

    created_by: TypeData = TypeData()


class LastEditedBy(PropertyType, type='last_edited_by'):
    """Defines the last-edited-by configuration for a database property."""

    class TypeData(GenericObject): ...

    last_edited_by: TypeData = TypeData()


class LastEditedTime(PropertyType, type='last_edited_time'):
    """Defines the last-edited-time configuration for a database property."""

    class TypeData(GenericObject): ...

    last_edited_time: TypeData = TypeData()


class UniqueID(PropertyType, type='unique_id'):
    """Unique ID database property."""

    class TypeData(GenericObject):
        prefix: str | None = None

    unique_id: TypeData = TypeData()


class Verification(PropertyType, type='verification'):
    """Verfication database property of Wiki databases."""

    class TypeData(GenericObject): ...

    verification: TypeData = TypeData()


class RenameProp(GenericObject):
    """Use to rename a property during a database update."""

    name: str

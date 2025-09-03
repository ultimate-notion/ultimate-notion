"""Objects representing a database schema.

Properties are used when

1. a database with a specific schema is [created],
2. a database with a schema is [retrieved].

Unfortunately, the way a schema is defined in case of 1. and 2. is not consistent.
In case 1., the property name is only defined as a key while in case 2. it is additionally
defined as `name` attribute of the property object. We treat these two cases the same way
when constructing the property objects. For this reason `name` is `Unset` by default.

[created]: https://developers.notion.com/reference/property-schema-object
[retrieved]: https://developers.notion.com/reference/property-object
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator
from typing_extensions import TypeVar

from ultimate_notion.obj_api.core import GenericObject, TypedObject, Unset, UnsetType
from ultimate_notion.obj_api.enums import AggFunc, NumberFormat
from ultimate_notion.obj_api.objects import SelectGroup, SelectOption

# ToDo: Use new syntax when requires-python >= 3.12
GO_co = TypeVar('GO_co', bound=GenericObject, covariant=True, default=GenericObject)


class Property(TypedObject[GO_co], polymorphic_base=True):
    """Base class for Notion property objects."""

    id: str | UnsetType = Unset
    name: str | UnsetType = Unset  # Unset when creating a database property schema
    description: str | None = None


class TitleTypeData(GenericObject):
    """Type data for `Title`."""


class Title(Property[TitleTypeData], type='title'):
    """Defines the title configuration for a database property."""

    title: TitleTypeData = Field(default_factory=TitleTypeData)


class RichTextTypeData(GenericObject):
    """Type data for `RichText`."""


class RichText(Property[RichTextTypeData], type='rich_text'):
    """Defines the rich text configuration for a database property."""

    rich_text: RichTextTypeData = Field(default_factory=RichTextTypeData)


class NumberTypeData(GenericObject):
    """Type data for `Number`."""

    format: NumberFormat = NumberFormat.NUMBER

    # leads to better error messages, see
    # https://github.com/pydantic/pydantic/issues/355
    @field_validator('format')
    @classmethod
    def validate_enum_field(cls, field: str) -> NumberFormat:
        return NumberFormat(field)


class Number(Property[NumberTypeData], type='number'):
    """Defines the number configuration for a database property."""

    number: NumberTypeData = Field(default_factory=NumberTypeData)

    @classmethod
    def build(cls, format: NumberFormat) -> Number:  # noqa: A002
        """Create a `Number` object with the expected format."""
        return cls.model_construct(number=NumberTypeData(format=format))


class SelectTypeData(GenericObject):
    """Type data for `Select`."""

    options: list[SelectOption] = Field(default_factory=list)


class Select(Property[SelectTypeData], type='select'):
    """Defines the select configuration for a database property."""

    select: SelectTypeData = Field(default_factory=SelectTypeData)

    @classmethod
    def build(cls, options: list[SelectOption]) -> Select:
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls.model_construct(select=SelectTypeData(options=options))


class MultiSelectTypeData(GenericObject):
    """Type data for `MultiSelect`."""

    options: list[SelectOption] = Field(default_factory=list)


class MultiSelect(Property[MultiSelectTypeData], type='multi_select'):
    """Defines the multi-select configuration for a database property."""

    multi_select: MultiSelectTypeData = Field(default_factory=MultiSelectTypeData)

    @classmethod
    def build(cls, options: list[SelectOption]) -> MultiSelect:
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls.model_construct(multi_select=MultiSelectTypeData(options=options))


class StatusTypeData(GenericObject):
    """Type data for `Status`."""

    options: list[SelectOption] = Field(default_factory=list)
    groups: list[SelectGroup] = Field(default_factory=list)


class Status(Property[StatusTypeData], type='status'):
    """Defines the status configuration for a database property."""

    status: StatusTypeData = Field(default_factory=StatusTypeData)

    @classmethod
    def build(cls, options: list[SelectOption], groups: list[SelectGroup]) -> Status:
        """Create a `Status` object from the list of `SelectOption`'s.

        !!! warning

            While a Status property can be built, it can only be used to
            check a schema, not to create a database having such a property.
        """
        return cls.model_construct(status=StatusTypeData(options=options, groups=groups))


class DateTypeData(GenericObject):
    """Type data for `Date`."""


class Date(Property[DateTypeData], type='date'):
    """Defines the date configuration for a database property."""

    date: DateTypeData = Field(default_factory=DateTypeData)


class PeopleTypeData(GenericObject):
    """Type data for `People`."""


class People(Property[PeopleTypeData], type='people'):
    """Defines the people configuration for a database property."""

    people: PeopleTypeData = Field(default_factory=PeopleTypeData)


class FilesTypeData(GenericObject):
    """Type data for `Files`."""


class Files(Property[FilesTypeData], type='files'):
    """Defines the files configuration for a database property."""

    files: FilesTypeData = Field(default_factory=FilesTypeData)


class CheckboxTypeData(GenericObject):
    """Type data for `Checkbox`."""


class Checkbox(Property[CheckboxTypeData], type='checkbox'):
    """Defines the checkbox configuration for a database property."""

    checkbox: CheckboxTypeData = Field(default_factory=CheckboxTypeData)


class EmailTypeData(GenericObject):
    """Type data for `Email`."""


class Email(Property[EmailTypeData], type='email'):
    """Defines the email configuration for a database property."""

    email: EmailTypeData = Field(default_factory=EmailTypeData)


class URLTypeData(GenericObject):
    """Type data for `URL`."""


class URL(Property[URLTypeData], type='url'):
    """Defines the URL configuration for a database property."""

    url: URLTypeData = Field(default_factory=URLTypeData)


class PhoneNumberTypeData(GenericObject):
    """Type data for `PhoneNumber`."""


class PhoneNumber(Property[PhoneNumberTypeData], type='phone_number'):
    """Defines the phone number configuration for a database property."""

    phone_number: PhoneNumberTypeData = Field(default_factory=PhoneNumberTypeData)


class FormulaTypeData(GenericObject):
    """Type data for `Formula`."""

    expression: str

    def __eq__(self, other: object) -> bool:
        """Compare Formula objects by all attributes except id."""
        # Sadly, expressions are changed by the Notion API, e.g. 'prop("Name")' in our request becomes
        # {{notion:block_property:title:00000000-0000-0000-0000-000000000000:5a65efbd-bfb2-4ebe-bb5d-ac95c98fb252}}
        # ToDo: Implement a way to compare these expressions, which is possible in principle.
        return isinstance(other, FormulaTypeData)

    def __hash__(self) -> int:
        """Return a hash of the Formula TypeData.

        Since __eq__ always returns True due to API expression transformation,
        we use a constant hash to maintain consistency with equality.
        """
        return hash(self.__class__)


class Formula(Property[FormulaTypeData], type='formula'):
    """Defines the formula configuration for a database property."""

    formula: FormulaTypeData

    @classmethod
    def build(cls, formula: str) -> Formula:
        return cls.model_construct(formula=FormulaTypeData(expression=formula))


class PropertyRelation(TypedObject[GO_co], polymorphic_base=True):
    """Defines common configuration for a property relation."""

    database_id: UUID
    data_source_id: str | None = None  # 2025-09-03 update: https://developers.notion.com/docs/upgrade-guide-2025-09-03

    def __eq__(self, other: object) -> bool:
        # ToDo: Consider data_source_id when Update 2025-09-03 is implemented.
        if not isinstance(other, PropertyRelation):
            return NotImplemented
        return self.database_id == other.database_id

    def __hash__(self) -> int:
        return hash(self.database_id)


class SinglePropertyRelationTypeData(GenericObject):
    """Type data for `SinglePropertyRelation`."""


class SinglePropertyRelation(PropertyRelation[SinglePropertyRelationTypeData], type='single_property'):
    """Defines a one-way relation configuration for a database property."""

    single_property: SinglePropertyRelationTypeData = Field(default_factory=SinglePropertyRelationTypeData)

    @classmethod
    def build_relation(cls, dbref: UUID) -> Relation:
        """Create a `single_property` relation using the target database reference.

        `dbref` must be either a string or UUID.
        """
        rel = SinglePropertyRelation.model_construct(database_id=dbref)
        return Relation.model_construct(relation=rel)


class DualPropertyRelationTypeData(GenericObject):
    """Type data for `DualPropertyRelation`."""

    synced_property_name: str | UnsetType = Unset
    synced_property_id: str | UnsetType = Unset

    def __eq__(self, other: object) -> bool:
        """Compare DualPropertyRelation objects by all attributes except id."""
        if not isinstance(other, DualPropertyRelationTypeData):
            return NotImplemented
        # we skip the id as this is set by the Notion API.
        return self.synced_property_name == other.synced_property_name

    def __hash__(self) -> int:
        """Return a hash of the DualPropertyRelation TypeData based on synced_property_name."""
        return hash(self.synced_property_name)


class DualPropertyRelation(PropertyRelation[DualPropertyRelationTypeData], type='dual_property'):
    """Defines a two-way relation configuration for a database property.

    If a two-way relation property X relates to Y then the two-way relation property Y relates to X.
    """

    dual_property: DualPropertyRelationTypeData = Field(default_factory=DualPropertyRelationTypeData)

    @classmethod
    def build_relation(cls, dbref: UUID) -> Relation:
        """Create a `dual_property` relation using the target database reference.

        `dbref` must be either a string or UUID.
        """
        # No `synced_property_name` is set since it will be ignored by the Notion API.
        # Thus we first get the default two-way relation name, which we gonna change later.
        # See: https://developers.notion.com/reference/property-schema-object#dual-property-relation-configuration
        rel = DualPropertyRelation.model_construct(database_id=dbref)
        return Relation.model_construct(relation=rel)


class Relation(Property[SinglePropertyRelation | DualPropertyRelation], type='relation'):
    """Defines the relation configuration for a database property."""

    relation: SinglePropertyRelation | DualPropertyRelation


class RollupTypeData(GenericObject):
    """Type data for `Rollup`."""

    function: AggFunc = AggFunc.COUNT_ALL

    relation_property_name: str
    relation_property_id: str | UnsetType = Unset

    rollup_property_name: str
    rollup_property_id: str | UnsetType = Unset

    # leads to better error messages, see
    # https://github.com/pydantic/pydantic/issues/355
    @field_validator('function')
    @classmethod
    def validate_enum_field(cls, field: str) -> AggFunc:
        return AggFunc(field)

    def __eq__(self, value: object) -> bool:
        """Compare Rollup objects by all attributes except id."""
        if not isinstance(value, RollupTypeData):
            return NotImplemented
        return (
            self.function == value.function
            and self.relation_property_name == value.relation_property_name
            and self.rollup_property_name == value.rollup_property_name
        )

    def __hash__(self) -> int:
        """Return a hash of the Rollup TypeData based on function and property names."""
        return hash((self.function, self.relation_property_name, self.rollup_property_name))


class Rollup(Property[RollupTypeData], type='rollup'):
    """Defines the rollup configuration for a database property."""

    rollup: RollupTypeData

    @classmethod
    def build(cls, relation: str, property: str, function: AggFunc) -> Rollup:  # noqa: A002
        return Rollup.model_construct(
            rollup=RollupTypeData(function=function, relation_property_name=relation, rollup_property_name=property)
        )


class CreatedTimeTypeData(GenericObject):
    """Type data for `CreatedTime`."""


class CreatedTime(Property[CreatedTimeTypeData], type='created_time'):
    """Defines the created-time configuration for a database property."""

    created_time: CreatedTimeTypeData = Field(default_factory=CreatedTimeTypeData)


class CreatedByTypeData(GenericObject):
    """Type data for `CreatedBy`."""


class CreatedBy(Property[CreatedByTypeData], type='created_by'):
    """Defines the created-by configuration for a database property."""

    created_by: CreatedByTypeData = Field(default_factory=CreatedByTypeData)


class LastEditedByTypeData(GenericObject):
    """Type data for `LastEditedBy`."""


class LastEditedBy(Property[LastEditedByTypeData], type='last_edited_by'):
    """Defines the last-edited-by configuration for a database property."""

    last_edited_by: LastEditedByTypeData = Field(default_factory=LastEditedByTypeData)


class LastEditedTimeTypeData(GenericObject):
    """Type data for `LastEditedTime`."""


class LastEditedTime(Property[LastEditedTimeTypeData], type='last_edited_time'):
    """Defines the last-edited-time configuration for a database property."""

    last_edited_time: LastEditedTimeTypeData = Field(default_factory=LastEditedTimeTypeData)


class UniqueIDTypeData(GenericObject):
    """Type data for `UniqueID`."""

    prefix: str | None = None


class UniqueID(Property[UniqueIDTypeData], type='unique_id'):
    """Unique ID database property."""

    unique_id: UniqueIDTypeData = Field(default_factory=UniqueIDTypeData)


class VerificationTypeData(GenericObject):
    """Type data for `Verification`."""


class Verification(Property[VerificationTypeData], type='verification'):
    """Verfication database property of Wiki databases."""

    verification: VerificationTypeData = Field(default_factory=VerificationTypeData)


class ButtonTypeData(GenericObject):
    """Type data for `Button`."""


class Button(Property[ButtonTypeData], type='button'):
    """Button database property."""

    button: ButtonTypeData = Field(default_factory=ButtonTypeData)


class RenameProp(GenericObject):
    """Property to rename a property during a database update."""

    name: str

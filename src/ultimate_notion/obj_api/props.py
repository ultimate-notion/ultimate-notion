"""Wrapper for property values of pages"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import TypeAlias

from pydantic import SerializeAsAny, field_validator

from ultimate_notion.obj_api.core import GenericObject, NotionObject
from ultimate_notion.obj_api.enums import VerificationState
from ultimate_notion.obj_api.objects import DateRange, FileObject, ObjectReference, RichTextObject, TypedObject, User
from ultimate_notion.obj_api.schema import Function, SelectOption

#: Notion's complex `Date` type, which is either a date or without time or a date range of the former.
DateType: TypeAlias = datetime | date | tuple[datetime | date, datetime | date]


class PropertyValue(TypedObject, polymorphic_base=True):
    """Base class for Notion property values."""

    id: str | None = None  # noqa: A003

    @classmethod
    def build(cls, value):
        """Build the property value from given value, e.g. native Python or nested type.

        In practice, this is like calling __init__ with the corresponding keyword.
        """
        return cls.model_construct(**{cls.model_fields['type'].get_default(): value})


class Title(PropertyValue, type='title'):
    """Notion title type."""

    title: list[SerializeAsAny[RichTextObject]] = None


class RichText(PropertyValue, type='rich_text'):
    """Notion rich text type."""

    rich_text: list[SerializeAsAny[RichTextObject]] = None


class Number(PropertyValue, type='number'):
    """Simple number type."""

    number: float | int | None = None  # ToDo: Recheck if it should be int | float | None instead


class Checkbox(PropertyValue, type='checkbox'):
    """Simple checkbox type; represented as a boolean."""

    checkbox: bool | None = None


class Date(PropertyValue, type='date'):
    """Notion complex date type - may include timestamp and/or be a date range."""

    date: DateRange | None = None

    @classmethod
    def build(cls, start: datetime | date, end: datetime | date | None = None):
        """Create a new Date from the native values."""
        return cls.model_construct(date=DateRange(start=start, end=end))


class Status(PropertyValue, type='status'):
    """Notion status property."""

    status: SelectOption | None = None


class Select(PropertyValue, type='select'):
    """Notion select type."""

    select: SelectOption | None = None


class MultiSelect(PropertyValue, type='multi_select'):
    """Notion multi-select type."""

    multi_select: list[SelectOption] = None


class People(PropertyValue, type='people'):
    """Notion people type."""

    people: list[SerializeAsAny[User]] = None


class URL(PropertyValue, type='url'):
    """Notion URL type."""

    url: str | None = None


class Email(PropertyValue, type='email'):
    """Notion email type."""

    email: str | None = None


class PhoneNumber(PropertyValue, type='phone_number'):
    """Notion phone type."""

    phone_number: str | None = None


class Files(PropertyValue, type='files'):
    """Notion files type."""

    files: list[SerializeAsAny[FileObject]] = None


class FormulaResult(TypedObject, ABC, polymorphic_base=True):
    """A Notion formula result.

    This object contains the result of the expression in the database properties.
    """

    @property
    @abstractmethod
    def value(self):
        """Return the result of this FormulaResult."""


class StringFormula(FormulaResult, type='string'):
    """A Notion string formula result."""

    string: str | None = None

    @property
    def value(self):
        return self.string


class NumberFormula(FormulaResult, type='number'):
    """A Notion number formula result."""

    number: float | int | None = None

    @property
    def value(self):
        return self.number


class DateFormula(FormulaResult, type='date'):
    """A Notion date formula result."""

    date: DateRange | None = None

    @property
    def value(self) -> None | DateType:
        if self.date is None:
            return None
        elif self.date.end is None:
            return self.date.start
        else:
            return self.date.start, self.date.end


class BooleanFormula(FormulaResult, type='boolean'):
    """A Notion boolean formula result."""

    boolean: bool | None = None

    @property
    def value(self):
        return self.boolean


class Formula(PropertyValue, type='formula'):
    """A Notion formula property value."""

    formula: FormulaResult | None = None


class Relation(PropertyValue, type='relation'):
    """A Notion relation property value."""

    relation: list[ObjectReference] = None
    has_more: bool = False

    @classmethod
    def build(cls, pages):
        """Return a `Relation` property with the specified pages."""
        return cls.model_construct(relation=[ObjectReference.build(page) for page in pages])


class RollupObject(TypedObject, ABC, polymorphic_base=True):
    """A Notion rollup property value."""

    function: Function | None = None

    @property
    @abstractmethod
    def value(self):
        """Return the native representation of this Rollup object."""


class RollupNumber(RollupObject, type='number'):
    """A Notion rollup number property value."""

    number: float | int | None = None

    @property
    def value(self) -> float | int | None:
        """Return the native representation of this Rollup object."""
        return self.number


class RollupDate(RollupObject, type='date'):
    """A Notion rollup date property value."""

    date: DateRange | None = None

    @property
    def value(self) -> DateType | None:
        if self.date is None:
            return None
        elif self.date.end is None:
            return self.date.start
        else:
            return self.date.start, self.date.end


class RollupArray(RollupObject, type='array'):
    """A Notion rollup array property value."""

    array: list[PropertyValue]

    @property
    def value(self) -> list[PropertyValue]:
        """Return the native representation of this Rollup object."""
        return self.array


class Rollup(PropertyValue, type='rollup'):
    """A Notion rollup property value."""

    rollup: RollupObject | None = None


class CreatedTime(PropertyValue, type='created_time'):
    """A Notion created-time property value."""

    created_time: datetime


class CreatedBy(PropertyValue, type='created_by'):
    """A Notion created-by property value."""

    created_by: SerializeAsAny[User]


class LastEditedTime(PropertyValue, type='last_edited_time'):
    """A Notion last-edited-time property value."""

    last_edited_time: datetime


class LastEditedBy(PropertyValue, type='last_edited_by'):
    """A Notion last-edited-by property value."""

    last_edited_by: SerializeAsAny[User]


class UniqueID(PropertyValue, type='unique_id'):
    """A Notion unique-id property value."""

    class _NestedData(GenericObject):
        number: int = 0
        prefix: str | None = None

    unique_id: _NestedData = _NestedData()


class Verification(PropertyValue, type='verification'):
    """A Notion verification property value"""

    class _NestedData(GenericObject):
        state: VerificationState = VerificationState.UNVERIFIED
        verified_by: SerializeAsAny[User] | None = None
        date: datetime | None = None

        # leads to better error messages, see
        # https://github.com/pydantic/pydantic/issues/355
        @field_validator('state')
        @classmethod
        def validate_enum_field(cls, field: str):
            return VerificationState(field)

    verification: _NestedData = _NestedData()


# https://developers.notion.com/reference/property-item-object
class PropertyItem(NotionObject, PropertyValue, object='property_item'):
    """A `PropertyItem` returned by the Notion API.

    Basic property items have a similar schema to corresponding property values.  As a
    result, these items share the `PropertyValue` type definitions.

    This class provides a placeholder for parsing property items, however objects
    parse by this class will likely be `PropertyValue`'s instead.
    """

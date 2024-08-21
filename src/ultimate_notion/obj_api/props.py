"""Wrapper for property values of pages"""

from __future__ import annotations

import datetime as dt
from abc import ABC
from typing import Any

import pendulum as pnd
from pydantic import SerializeAsAny, field_validator, model_serializer

from ultimate_notion.obj_api.core import GenericObject, NotionObject
from ultimate_notion.obj_api.enums import VState
from ultimate_notion.obj_api.objects import (
    DateRange,
    FileObject,
    ObjectReference,
    RichTextBaseObject,
    TypedObject,
    User,
)
from ultimate_notion.obj_api.schema import AggFunc, SelectOption


class PropertyValue(TypedObject, polymorphic_base=True):
    """Base class for Notion property values."""

    id: str = None  # type: ignore

    @classmethod
    def build(cls, value):
        """Build the property value from given value, e.g. native Python or nested type.

        In practice, this is like calling __init__ with the corresponding keyword.
        """
        return cls.model_construct(**{cls.model_fields['type'].get_default(): value})

    def serialize_for_api(self):
        """Serialize the object for sending it to the Notion API."""
        # TODO: read-only fields should not be sent to the API
        # https://github.com/jheddings/notional/issues/9

        # We include "null" values as those are used to delete properties
        dump_dct = self.model_dump(mode='json', exclude_none=True, by_alias=True)
        dump_dct.setdefault(dump_dct['type'], None)
        return dump_dct


class Title(PropertyValue, type='title'):
    """Notion title type."""

    title: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore


class RichText(PropertyValue, type='rich_text'):
    """Notion rich text type."""

    rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore


class Number(PropertyValue, type='number'):
    """Simple number type."""

    number: float | int | None = None


class Checkbox(PropertyValue, type='checkbox'):
    """Simple checkbox type; represented as a boolean."""

    checkbox: bool | None = None


class Date(PropertyValue, type='date'):
    """Notion complex date type - may include timestamp and/or be a date range."""

    date: DateRange | None = None

    @classmethod
    def build(cls, dt_spec: dt.datetime | dt.date | pnd.Interval):
        """Create a new Date from the native values."""
        return cls.model_construct(date=DateRange.build(dt_spec))


class Status(PropertyValue, type='status'):
    """Notion status property."""

    status: SelectOption | None = None


class Select(PropertyValue, type='select'):
    """Notion select type."""

    select: SelectOption | None = None


class MultiSelect(PropertyValue, type='multi_select'):
    """Notion multi-select type."""

    multi_select: list[SelectOption] = None  # type: ignore


class People(PropertyValue, type='people'):
    """Notion people type."""

    people: list[User] = None  # type: ignore

    # Custom serializer as we receive various UserRef subtypes but need to pass
    # a proper UserRef to the Notion API. Notion API is just so inconsistent!
    @model_serializer
    def serialize(self) -> dict[str, Any]:
        return {'people': [{'id': user.id, 'object': user.object} for user in self.people], 'type': 'people'}


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

    files: list[SerializeAsAny[FileObject]] = None  # type: ignore


class FormulaResult(TypedObject, ABC, polymorphic_base=True):
    """A Notion formula result.

    This object contains the result of the expression in the database properties.
    """


class StringFormula(FormulaResult, type='string'):
    """A Notion string formula result."""

    string: str | None = None


class NumberFormula(FormulaResult, type='number'):
    """A Notion number formula result."""

    number: float | int | None = None


class DateFormula(FormulaResult, type='date'):
    """A Notion date formula result."""

    date: DateRange | None = None


class BooleanFormula(FormulaResult, type='boolean'):
    """A Notion boolean formula result."""

    boolean: bool | None = None


class Formula(PropertyValue, type='formula'):
    """A Notion formula property value."""

    formula: FormulaResult | None = None


class Relation(PropertyValue, type='relation'):
    """A Notion relation property value."""

    relation: list[ObjectReference] = None  # type: ignore
    has_more: bool = False

    @classmethod
    def build(cls, pages):
        """Return a `Relation` property with the specified pages."""
        return cls.model_construct(relation=[ObjectReference.build(page) for page in pages])


class RollupObject(TypedObject, ABC, polymorphic_base=True):
    """A Notion rollup property value."""

    function: AggFunc | None = None


class RollupNumber(RollupObject, type='number'):
    """A Notion rollup number property value."""

    number: float | int | None = None


class RollupDate(RollupObject, type='date'):
    """A Notion rollup date property value."""

    date: DateRange | None = None


class RollupArray(RollupObject, type='array'):
    """A Notion rollup array property value."""

    array: list[PropertyValue]


class Rollup(PropertyValue, type='rollup'):
    """A Notion rollup property value."""

    rollup: RollupObject | None = None


class CreatedTime(PropertyValue, type='created_time'):
    """A Notion created-time property value."""

    created_time: dt.datetime


class CreatedBy(PropertyValue, type='created_by'):
    """A Notion created-by property value."""

    created_by: SerializeAsAny[User]


class LastEditedTime(PropertyValue, type='last_edited_time'):
    """A Notion last-edited-time property value."""

    last_edited_time: dt.datetime


class LastEditedBy(PropertyValue, type='last_edited_by'):
    """A Notion last-edited-by property value."""

    last_edited_by: SerializeAsAny[User]


class UniqueID(PropertyValue, type='unique_id'):
    """A Notion unique-id property value."""

    class TypeData(GenericObject):
        number: int = 0
        prefix: str | None = None

    unique_id: TypeData = TypeData()


class Verification(PropertyValue, type='verification'):
    """A Notion verification property value."""

    class TypeData(GenericObject):
        state: VState = VState.UNVERIFIED
        verified_by: SerializeAsAny[User] | None = None
        date: dt.datetime | None = None

        # leads to better error messages, see
        # https://github.com/pydantic/pydantic/issues/355
        @field_validator('state')
        @classmethod
        def validate_enum_field(cls, field: str):
            return VState(field)

    verification: TypeData = TypeData()


class PropertyItem(NotionObject, PropertyValue, object='property_item'):
    """A `PropertyItem` returned by the Notion API.

    Basic property items have a similar schema to corresponding property values.  As a
    result, these items share the `PropertyValue` type definitions.

    This class provides a placeholder for parsing property items, however objects
    parse by this class will likely be `PropertyValue`'s instead.

    Notion-API: https://developers.notion.com/reference/property-item-object
    """

    id: str

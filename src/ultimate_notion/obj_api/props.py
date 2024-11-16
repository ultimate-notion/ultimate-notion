"""Property values of a page in Notion directly mapped to Python objects."""

from __future__ import annotations

import datetime as dt
from abc import ABC
from typing import Any

import pendulum as pnd
from pydantic import SerializeAsAny, field_validator, model_serializer

from ultimate_notion.obj_api.core import GenericObject, NotionObject
from ultimate_notion.obj_api.enums import FormulaType, RollupType, VState
from ultimate_notion.obj_api.objects import (
    DateRange,
    FileObject,
    ObjectRef,
    RichTextBaseObject,
    TypedObject,
    User,
)
from ultimate_notion.obj_api.schema import AggFunc, SelectOption

MAX_ITEMS_PER_PROPERTY = 25
"""Maximum number of items rertrieved per property.

Only a certain number of items for each property are retrieved by default.
The high-level API will retrieve the rest on demand automatically.

Source: https://developers.notion.com/reference/retrieve-a-page
"""


class PropertyValue(TypedObject, polymorphic_base=True):
    """Base class for Notion property values."""

    id: str = None  # type: ignore
    _is_retrieved: bool = False  # fetched separately as property item from the server

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
    def build(cls, dt_spec: str | dt.datetime | dt.date | pnd.Interval):
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


class StringFormula(FormulaResult, type=FormulaType.STRING.value):
    """A Notion string formula result."""

    string: str | None = None


class NumberFormula(FormulaResult, type=FormulaType.NUMBER.value):
    """A Notion number formula result."""

    number: float | int | None = None


class DateFormula(FormulaResult, type=FormulaType.DATE.value):
    """A Notion date formula result."""

    date: DateRange | None = None


class BooleanFormula(FormulaResult, type=FormulaType.BOOLEAN.value):
    """A Notion boolean formula result."""

    boolean: bool | None = None


class Formula(PropertyValue, type='formula'):
    """A Notion formula property value."""

    formula: FormulaResult | None = None


class Relation(PropertyValue, type='relation'):
    """A Notion relation property value."""

    relation: list[ObjectRef] = None  # type: ignore
    has_more: bool = False

    @classmethod
    def build(cls, pages):
        """Return a `Relation` property with the specified pages."""
        return cls.model_construct(relation=[ObjectRef.build(page) for page in pages])


class RollupObject(TypedObject, ABC, polymorphic_base=True):
    """A Notion rollup property value."""

    function: AggFunc | None = None


class RollupNumber(RollupObject, type=RollupType.NUMBER.value):
    """A Notion rollup number property value."""

    number: float | int | None = None


class RollupDate(RollupObject, type=RollupType.DATE.value):
    """A Notion rollup date property value."""

    date: DateRange | None = None


class RollupArray(RollupObject, type=RollupType.ARRAY.value):
    """A Notion rollup array property value."""

    array: list[SerializeAsAny[PropertyValue]]


class RollupIncomplete(RollupObject, type=RollupType.INCOMPLETE.value):
    """A Notion incomplete rollup property value."""

    class TypeData(GenericObject): ...

    incomplete: TypeData


class RollupUnsupported(RollupObject, type=RollupType.UNSUPPORTED.value):
    """A Notion unsupported rollup property value."""

    class TypeData(GenericObject): ...

    unsupported: TypeData


class Rollup(PropertyValue, type='rollup'):
    """A Notion rollup property value."""

    rollup: SerializeAsAny[RollupObject] | None = None


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


class PropertyItem(NotionObject, TypedObject, polymorphic_base=True, object='property_item'):
    """A `PropertyItem` returned by the Notion API.

    Basic property items have a similar schema to corresponding property values.

    Notion-API: https://developers.notion.com/reference/property-item-object
    """

    id: str


class TitlePropertyItem(PropertyItem, type='title'):
    """A `PropertyItem` returned by the Notion API containing the `Title` property."""

    title: SerializeAsAny[RichTextBaseObject]


class RichTextPropertyItem(PropertyItem, type='rich_text'):
    """A `PropertyItem` returned by the Notion API containing the `RichText` property."""

    rich_text: SerializeAsAny[RichTextBaseObject]


class NumberPropertyItem(PropertyItem, Number, type='number'):
    """A `PropertyItem` returned by the Notion API containing the `Number` property."""


class CheckboxPropertyItem(PropertyItem, Checkbox, type='checkbox'):
    """A `PropertyItem` returned by the Notion API containing the `Checkbox` property."""


class DatePropertyItem(PropertyItem, Date, type='date'):
    """A `PropertyItem` returned by the Notion API containing the `Date` property."""


class StatusPropertyItem(PropertyItem, Status, type='status'):
    """A `PropertyItem` returned by the Notion API containing the `Status` property."""


class SelectPropertyItem(PropertyItem, Select, type='select'):
    """A `PropertyItem` returned by the Notion API containing the `Select` property."""


class MultiSelectPropertyItem(PropertyItem, MultiSelect, type='multi_select'):
    """A `PropertyItem` returned by the Notion API containing the `MultiSelect` property."""


class PeoplePropertyItem(PropertyItem, type='people'):
    """A `PropertyItem` returned by the Notion API containing the `People` property."""

    people: User


class URLPropertyItem(PropertyItem, URL, type='url'):
    """A `PropertyItem` returned by the Notion API containing the `URL` property."""


class EmailPropertyItem(PropertyItem, Email, type='email'):
    """A `PropertyItem` returned by the Notion API containing the `Email` property."""


class PhoneNumberPropertyItem(PropertyItem, PhoneNumber, type='phone_number'):
    """A `PropertyItem` returned by the Notion API containing the `PhoneNumber` property."""


class FilesPropertyItem(PropertyItem, Files, type='files'):
    """A `FilesPropertyItem` returned by the Notion API containing the `Files` property."""


class FormulaPropertyItem(PropertyItem, Formula, type='formula'):
    """A `PropertyItem` returned by the Notion API containing the `Formula` property."""


class RelationPropertyItem(PropertyItem, type='relation'):
    """A `PropertyItem` returned by the Notion API containing many `Relation` properties."""

    relation: ObjectRef


class RollupPropertyItem(PropertyItem, Rollup, type='rollup'):
    """A `PropertyItem` returned by the Notion API containing the `Rollup` property."""


class CreatedTimePropertyItem(PropertyItem, CreatedTime, type='created_time'):
    """A `PropertyItem` returned by the Notion API containing the `CreatedTime` property."""


class CreatedByPropertyItem(PropertyItem, CreatedBy, type='created_by'):
    """A `PropertyItem` returned by the Notion API containing the `CreatedBy` property."""


class LastEditedTimePropertyItem(PropertyItem, LastEditedTime, type='last_edited_time'):
    """A `PropertyItem` returned by the Notion API containing the `LastEditedTime` property."""


class LastEditedByPropertyItem(PropertyItem, LastEditedBy, type='last_edited_by'):
    """A `PropertyItem` returned by the Notion API containing the `LastEditedBy` property."""


class UniqueIDPropertyItem(PropertyItem, UniqueID, type='unique_id'):
    """A `PropertyItem` returned by the Notion API containing the `UniqueID` property."""


class VerificationPropertyItem(PropertyItem, Verification, type='verification'):
    """A `PropertyItem` returned by the Notion API containing the `Verification` property."""


PAGINATED_PROP_VALS = (RichText, Title, People, Relation, Rollup)
f"""Property values that are potentially paginated when exceeding {MAX_ITEMS_PER_PROPERTY} of
inline page/person mentions or items and need to be fetched seperately from the server.

Source: https://developers.notion.com/reference/retrieve-a-page#limits
"""

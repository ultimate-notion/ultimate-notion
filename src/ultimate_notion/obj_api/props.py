"""Property values of a page in Notion directly mapped to Python objects.

`PropertyValue` objects are directly returned from the Notion API using the [retrieve a page] endpoint.
They are used to represent the values of a page's properties. In contrast the `PropertyItem` objects
are returned from the [retrieve a page property item] endpoint and differ from the `PropertyValue` objects
by having a field `object = 'property_item'`. So they are considered *proper* objects in the Notion API
instead of just types like the `PropertyValue` objects.

[retrieve a page]: https://developers.notion.com/reference/retrieve-a-page
[retrieve a page property item]: https://developers.notion.com/reference/retrieve-a-page-property
"""

from __future__ import annotations

import datetime as dt
from abc import ABC
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from pydantic import Field, SerializeAsAny, field_validator, model_serializer
from typing_extensions import Self

from ultimate_notion.obj_api.core import GenericObject, NotionObject, Unset, UnsetType
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
from ultimate_notion.utils import DateTimeOrRange

if TYPE_CHECKING:
    from ultimate_notion.obj_api.blocks import Page

MAX_ITEMS_PER_PROPERTY = 25
"""Maximum number of items rertrieved per property.

Only a certain number of items for each property are retrieved by default.
The high-level API will retrieve the rest on demand automatically.

Source: https://developers.notion.com/reference/retrieve-a-page
"""

###################
# Property Values #
###################


class PropertyValue(TypedObject[Any], polymorphic_base=True):
    """Base class for Notion property values."""

    id: str | UnsetType = Unset
    _is_retrieved: bool = False  # fetched separately as property item from the server

    @classmethod
    def build(cls, value: Any) -> Self:
        """Build the property value from given value, e.g. native Python or nested type.

        In practice, this is like calling __init__ with the corresponding keyword.
        """
        return cast(Self, cls.model_construct(**{cls.model_fields['type'].get_default(): value}))

    def serialize_for_api(self) -> dict[str, Any]:
        """Serialize the object for sending it to the Notion API."""
        dump_dct = super().serialize_for_api()
        dump_dct.setdefault(dump_dct['type'], None)
        return dump_dct


class Title(PropertyValue, type='title'):
    """Notion title type."""

    title: list[SerializeAsAny[RichTextBaseObject]] = Field(default_factory=list)


class RichText(PropertyValue, type='rich_text'):
    """Notion rich text type."""

    rich_text: list[SerializeAsAny[RichTextBaseObject]] = Field(default_factory=list)


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
    def build(cls, dt_spec: str | DateTimeOrRange) -> Self:
        """Create a new Date from the native values."""
        return cast(Self, cls.model_construct(date=DateRange.build(dt_spec)))


class Status(PropertyValue, type='status'):
    """Notion status property."""

    status: SelectOption | None = None


class Select(PropertyValue, type='select'):
    """Notion select type."""

    select: SelectOption | None = None


class MultiSelect(PropertyValue, type='multi_select'):
    """Notion multi-select type."""

    multi_select: list[SelectOption] = Field(default_factory=list)


class People(PropertyValue, type='people'):
    """Notion people type."""

    people: list[User] = Field(default_factory=list)

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

    files: list[SerializeAsAny[FileObject]] = Field(default_factory=list)


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

    formula: SerializeAsAny[FormulaResult] | None = None


class Relation(PropertyValue, type='relation'):
    """A Notion relation property value."""

    relation: list[ObjectRef] = Field(default_factory=list)
    has_more: bool = False

    @classmethod
    def build(cls, pages: Sequence[Page]) -> Self:
        """Return a `Relation` property with the specified pages."""
        return cast(Self, cls.model_construct(relation=[ObjectRef.build(page) for page in pages]))


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

    unique_id: TypeData = Field(default_factory=TypeData)


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
        def validate_enum_field(cls, field: str) -> VState:
            return VState(field)

    verification: TypeData = Field(default_factory=TypeData)


class Button(PropertyValue, type='button'):
    """A Notion button property value."""

    class TypeData(GenericObject): ...

    button: TypeData = Field(default_factory=TypeData)


##################
# Property Items #
##################


class PropertyItem(NotionObject, TypedObject, polymorphic_base=True, object='property_item'):
    """A `PropertyItem` returned by the Notion API.

    Basic property items have a similar schema to corresponding property values.

    Notion-API: https://developers.notion.com/reference/property-item-object
    """

    id: str


class TitlePropertyItem(PropertyItem, type='title'):
    """A `PropertyItem` returned by the Notion API containing the `Title` property."""

    # According to the Notion API docs, this should be a list of rich text objects.
    # Nevertheless, the Notion API returns a single rich text object
    title: SerializeAsAny[RichTextBaseObject]


class RichTextPropertyItem(PropertyItem, type='rich_text'):
    """A `PropertyItem` returned by the Notion API containing the `RichText` property."""

    # According to the Notion API docs, this should be a list of rich text objects.
    # Nevertheless, the Notion API returns a single rich text object
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

    # According to the Notion API docs, this should be a list of people objects.
    # Nevertheless, the Notion API returns a single people object
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


class ButtonPropertyItem(PropertyItem, Button, type='button'):
    """A `PropertyItem` returned by the Notion API containing the `Button` property."""


PAGINATED_PROP_VALS = (RichText, Title, People, Relation, Rollup)
f"""Property values that are potentially paginated when exceeding {MAX_ITEMS_PER_PROPERTY} of
inline page/person mentions or items and need to be fetched seperately from the server.

Source: https://developers.notion.com/reference/retrieve-a-page#limits
"""

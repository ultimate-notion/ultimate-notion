"""Wrapper for Notion API data types.

Similar to other records, these object provide access to the primitive data structure
used in the Notion API as well as higher-level methods.
"""
# ToDo: Could this be split up into properties relating to the schema and actual types that are inline in blocks but also properties?


from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import List, Optional, Union
from uuid import UUID

from notion_client import helpers

from ultimate_notion.obj_api import util
from ultimate_notion.obj_api.core import GenericObject, NotionObject, TypedObject
from ultimate_notion.obj_api.schema import Function
from ultimate_notion.obj_api.text import Color, RichTextObject, plain_text, rich_text
from ultimate_notion.obj_api.user import User


class ObjectReference(GenericObject):
    """A general-purpose object reference in the Notion API."""

    id: UUID

    @classmethod
    def __compose__(cls, ref):
        """Compose an ObjectReference from the given reference.

        `ref` may be a `UUID`, `str`, `ParentRef` or `GenericObject` with an `id`.

        Strings may be either UUID's or URL's to Notion content.
        """

        if isinstance(ref, cls):
            return ref.copy(deep=True)

        if isinstance(ref, ParentRef):
            # ParentRef's are typed-objects with a nested UUID
            return ObjectReference(id=ref())

        if isinstance(ref, GenericObject) and hasattr(ref, "id"):
            # re-compose the ObjectReference from the internal ID
            return ObjectReference[ref.id]

        if isinstance(ref, UUID):
            return ObjectReference(id=ref)

        if isinstance(ref, str):
            ref = util.extract_id_from_string(ref)

            if ref is not None:
                return ObjectReference(id=UUID(ref))

        raise ValueError("Unrecognized 'ref' attribute")

    @property
    def URL(self):
        """Return the Notion URL for this object reference.

        Note: this is a convenience property only.  It does not guarantee that the
        URL exists or that it is accessible by the integration.
        """
        return helpers.get_url(self.id)


# https://developers.notion.com/reference/parent-object
class ParentRef(TypedObject):
    """Reference another block as a parent."""

    # note that this class is simply a placeholder for the typed concrete *Ref classes
    # callers should always instantiate the intended concrete versions


class DatabaseRef(ParentRef, type="database_id"):
    """Reference a database."""

    database_id: UUID

    @classmethod
    def __compose__(cls, db_ref):
        """Compose a DatabaseRef from the given reference object.

        `db_ref` can be either a string, UUID, or database.
        """
        ref = ObjectReference[db_ref]
        return DatabaseRef(database_id=ref.id)


class PageRef(ParentRef, type="page_id"):
    """Reference a page."""

    page_id: UUID

    @classmethod
    def __compose__(cls, page_ref):
        """Compose a PageRef from the given reference object.

        `page_ref` can be either a string, UUID, or page.
        """
        ref = ObjectReference[page_ref]
        return PageRef(page_id=ref.id)


class BlockRef(ParentRef, type="block_id"):
    """Reference a block."""

    block_id: UUID

    @classmethod
    def __compose__(cls, block_ref):
        """Compose a BlockRef from the given reference object.

        `block_ref` can be either a string, UUID, or block.
        """
        ref = ObjectReference[block_ref]
        return BlockRef(block_id=ref.id)


class WorkspaceRef(ParentRef, type="workspace"):
    """Reference the workspace."""

    workspace: bool = True


class EmojiObject(TypedObject, type="emoji"):
    """A Notion emoji object."""

    emoji: str

    def __str__(self):
        """Return this EmojiObject as a simple string."""
        return self.emoji

    @classmethod
    def __compose__(cls, emoji):
        """Compose an EmojiObject from the given emoji string."""
        return EmojiObject(emoji=emoji)


class FileObject(TypedObject):
    """A Notion file object.

    Depending on the context, a FileObject may require a name (such as in the `Files`
    property).  This makes the object hierarchy difficult, so here we simply allow
    `name` to be optional. It is the responsibility of the caller to set `name` if
    required by the API.
    """

    name: Optional[str] = None

    def __str__(self):
        """Return a string representation of this object."""
        return self.name or "__unknown__"

    @property
    def URL(self):
        """Return the URL to this FileObject."""
        return self("url")


class HostedFile(FileObject, type="file"):
    """A Notion file object."""

    class _NestedData(GenericObject):
        url: str
        expiry_time: Optional[datetime] = None

    file: _NestedData


class ExternalFile(FileObject, type="external"):
    """An external file object."""

    class _NestedData(GenericObject):
        url: str

    external: _NestedData

    def __str__(self):
        """Return a string representation of this object."""
        name = super().__str__()

        if self.external and self.external.url:
            return f"![{name}]({self.external.url})"

        return name

    @classmethod
    def __compose__(cls, url, name=None):
        """Create a new `ExternalFile` from the given URL."""
        return cls(name=name, external=cls._NestedData(url=url))


class DateRange(GenericObject):
    """A Notion date range, with an optional end date."""

    start: Union[date, datetime]
    end: Optional[Union[date, datetime]] = None

    def __str__(self):
        """Return a string representation of this object."""

        if self.end is None:
            return f"{self.start}"

        return f"{self.start} :: {self.end}"


class MentionData(TypedObject):
    """Base class for typed `Mention` data objects."""


class MentionUser(MentionData, type="user"):
    """Nested user data for `Mention` properties."""

    user: User

    @classmethod
    def __compose__(cls, user: User):
        """Build a `Mention` object for the specified user.

        The `id` field must be set for the given User.  Other fields may cause errors
        if they do not match the specific type returned from the API.
        """

        return MentionObject(plain_text=str(user), mention=MentionUser(user=user))


class MentionPage(MentionData, type="page"):
    """Nested page data for `Mention` properties."""

    page: ObjectReference

    @classmethod
    def __compose__(cls, page_ref):
        """Build a `Mention` object for the specified page reference."""

        ref = ObjectReference[page_ref]

        return MentionObject(plain_text=str(ref), mention=MentionPage(page=ref))


class MentionDatabase(MentionData, type="database"):
    """Nested database information for `Mention` properties."""

    database: ObjectReference

    @classmethod
    def __compose__(cls, page):
        """Build a `Mention` object for the specified database reference."""

        ref = ObjectReference[page]

        return MentionObject(plain_text=str(ref), mention=MentionDatabase(database=ref))


class MentionDate(MentionData, type="date"):
    """Nested date data for `Mention` properties."""

    date: DateRange

    @classmethod
    def __compose__(cls, start, end=None):
        """Build a `Mention` object for the specified URL."""

        date_obj = DateRange(start=start, end=end)

        return MentionObject(plain_text=str(date_obj), mention=MentionDate(date=date_obj))


class MentionLinkPreview(MentionData, type="link_preview"):
    """Nested url data for `Mention` properties.

    These objects cannot be created via the API.
    """

    class _NestedData(GenericObject):
        url: str

    link_preview: _NestedData


class MentionTemplateData(TypedObject):
    """Nested template data for `Mention` properties."""


class MentionTemplateDate(MentionTemplateData, type="template_mention_date"):
    """Nested date template data for `Mention` properties."""

    template_mention_date: str


class MentionTemplateUser(MentionTemplateData, type="template_mention_user"):
    """Nested user template data for `Mention` properties."""

    template_mention_user: str


class MentionTemplate(MentionData, type="template_mention"):
    """Nested template data for `Mention` properties."""

    template_mention: MentionTemplateData


class MentionObject(RichTextObject, type="mention"):
    """Notion mention element."""

    mention: MentionData


class EquationObject(RichTextObject, type="equation"):
    """Notion equation element."""

    class _NestedData(GenericObject):
        expression: str

    equation: _NestedData

    def __str__(self):
        """Return a string representation of this object."""

        if self.equation is None:
            return None

        return self.equation.expression


class NativeTypeMixin:
    """Mixin class for properties that can be represented as native Python types."""

    def __str__(self):
        """Return a string representation of this object."""

        value = self.Value

        if value is None:
            return ""

        return str(value)

    def __eq__(self, other):
        """Determine if this property is equal to the given object."""

        # if `other` is a NativeTypeMixin, this comparrison will call __eq__ on that
        # object using this objects `Value` as the value for `other` (allowing callers
        # to compare using either native types or NativeTypeMixin's)

        return other == self.Value

    def __ne__(self, other):
        """Determine if this property is not equal to the given object."""
        return not self.__eq__(other)

    @classmethod
    def __compose__(cls, value):
        """Build the property value from the native Python value."""

        # use type-name field to instantiate the class when possible
        if hasattr(cls, "type"):
            return cls(**{cls.type: value})

        raise NotImplementedError()

    @property
    def Value(self):
        """Get the current value of this property as a native Python type."""

        cls = self.__class__

        # check to see if the object has a field with the type-name
        # (this is assigned by TypedObject during subclass creation)
        if hasattr(cls, "type") and hasattr(self, cls.type):
            return getattr(self, cls.type)

        raise NotImplementedError()


class PropertyValue(TypedObject):
    """Base class for Notion property values."""

    id: Optional[str] = None


class Title(NativeTypeMixin, PropertyValue, type="title"):
    """Notion title type."""

    title: List[RichTextObject] = []

    def __len__(self):
        """Return the number of object in the Title object."""

        return len(self.title)

    @classmethod
    def __compose__(cls, *text):
        """Create a new `Title` property from the given text elements."""
        return cls(title=rich_text(*text))

    @property
    def Value(self):
        """Return the plain text from this Title."""

        if self.title is None:
            return None

        return plain_text(*self.title)


class RichText(NativeTypeMixin, PropertyValue, type="rich_text"):
    """Notion rich text type."""

    rich_text: List[RichTextObject] = []

    def __len__(self):
        """Return the number of object in the RichText object."""
        return len(self.rich_text)

    @classmethod
    def __compose__(cls, *text):
        """Create a new `RichText` property from the given strings."""
        return cls(rich_text=rich_text(*text))

    @property
    def Value(self):
        """Return the plain text from this RichText."""

        if self.rich_text is None:
            return None

        return plain_text(*self.rich_text)


class Number(NativeTypeMixin, PropertyValue, type="number"):
    """Simple number type."""

    number: Optional[Union[float, int]] = None

    def __float__(self):
        """Return the Number as a `float`."""

        if self.number is None:
            raise ValueError("Cannot convert 'None' to float")

        return float(self.number)

    def __int__(self):
        """Return the Number as an `int`."""

        if self.number is None:
            raise ValueError("Cannot convert 'None' to int")

        return int(self.number)

    def __iadd__(self, other):
        """Add the given value to this Number."""

        if isinstance(other, Number):
            self.number += other.Value
        else:
            self.number += other

        return self

    def __isub__(self, other):
        """Subtract the given value from this Number."""

        if isinstance(other, Number):
            self.number -= other.Value
        else:
            self.number -= other

        return self

    def __add__(self, other):
        """Add the value of `other` and returns the result as a Number."""
        return Number[other + self.Value]

    def __sub__(self, other):
        """Subtract the value of `other` and returns the result as a Number."""
        return Number[self.Value - float(other)]

    def __mul__(self, other):
        """Multiply the value of `other` and returns the result as a Number."""
        return Number[other * self.Value]

    def __le__(self, other):
        """Return `True` if this `Number` is less-than-or-equal-to `other`."""
        return self < other or self == other

    def __lt__(self, other):
        """Return `True` if this `Number` is less-than `other`."""
        return other > self.Value

    def __ge__(self, other):
        """Return `True` if this `Number` is greater-than-or-equal-to `other`."""
        return self > other or self == other

    def __gt__(self, other):
        """Return `True` if this `Number` is greater-than `other`."""
        return other < self.Value

    @property
    def Value(self):
        """Get the current value of this property as a native Python number."""
        return self.number


class Checkbox(NativeTypeMixin, PropertyValue, type="checkbox"):
    """Simple checkbox type; represented as a boolean."""

    checkbox: Optional[bool] = None


class Date(PropertyValue, type="date"):
    """Notion complex date type - may include timestamp and/or be a date range."""

    date: Optional[DateRange] = None

    def __contains__(self, other):
        """Determine if the given date is in the range (inclusive) of this Date.

        Raises ValueError if the Date object is not a range - e.g. has no end date.
        """

        if not self.IsRange:
            raise ValueError("This date is not a range")

        return self.Start <= other <= self.End

    def __str__(self):
        """Return a string representation of this property."""
        return "" if self.date is None else str(self.date)

    @classmethod
    def __compose__(cls, start, end=None):
        """Create a new Date from the native values."""
        return cls(date=DateRange(start=start, end=end))

    @property
    def IsRange(self):
        """Determine if this object represents a date range (versus a single date)."""

        if self.date is None:
            return False

        return self.date.end is not None

    @property
    def Start(self):
        """Return the start date of this property."""
        return None if self.date is None else self.date.start

    @property
    def End(self):
        """Return the end date of this property."""
        return None if self.date is None else self.date.end


class Status(NativeTypeMixin, PropertyValue, type="status"):
    """Notion status property."""

    class _NestedData(GenericObject):
        name: str = None
        id: Optional[Union[UUID, str]] = None
        color: Optional[Color] = None

    status: Optional[_NestedData] = None

    def __str__(self):
        """Return a string representation of this property."""
        return self.Value or ""

    def __eq__(self, other):
        """Determine if this property is equal to the given object.

        To avoid confusion, this method compares Status options by name.
        """

        if other is None:
            return self.status is None

        if isinstance(other, Status):
            return self.status.name == other.status.name

        return self.status.name == other

    @classmethod
    def __compose__(cls, name, color=None):
        """Create a `Status` property from the given name.

        :param name: a string to use for this property
        :param color: an optional Color for the status
        """

        if name is None:
            raise ValueError("'name' cannot be None")

        return cls(status=Status._NestedData(name=name, color=color))

    @property
    def Value(self):
        """Return the value of this property as a string."""

        return self.status.name


class SelectValue(GenericObject):
    """Values for select & multi-select properties."""

    name: str
    id: Optional[Union[UUID, str]] = None
    color: Optional[Color] = None

    def __str__(self):
        """Return a string representation of this property."""
        return self.name

    @classmethod
    def __compose__(cls, value, color=None):
        """Create a `SelectValue` property from the given value.

        :param value: a string to use for this property
        :param color: an optional Color for the value
        """
        return cls(name=value, color=color)


class SelectOne(NativeTypeMixin, PropertyValue, type="select"):
    """Notion select type."""

    select: Optional[SelectValue] = None

    def __str__(self):
        """Return a string representation of this property."""
        return self.Value or ""

    def __eq__(self, other):
        """Determine if this property is equal to the given object.

        To avoid confusion, this method compares Select options by name.
        """

        if other is None:
            return self.select is None

        return other == self.select.name

    @classmethod
    def __compose__(cls, value, color=None):
        """Create a `SelectOne` property from the given value.

        :param value: a string to use for this property
        :param color: an optional Color for the value
        """
        return cls(select=SelectValue[value, color])

    @property
    def Value(self):
        """Return the value of this property as a string."""

        if self.select is None:
            return None

        return str(self.select)


class MultiSelect(PropertyValue, type="multi_select"):
    """Notion multi-select type."""

    multi_select: List[SelectValue] = []

    def __str__(self):
        """Return a string representation of this property."""
        return ", ".join(self.Values)

    def __len__(self):
        """Count the number of selected values."""
        return len(self.multi_select)

    def __getitem__(self, index):
        """Return the SelectValue object at the given index."""

        if self.multi_select is None:
            raise IndexError("empty property")

        if index > len(self.multi_select):
            raise IndexError("index out of range")

        return self.multi_select[index]

    def __iadd__(self, other):
        """Add the given option to this MultiSelect."""

        if other in self:
            raise ValueError(f"Duplicate item: {other}")

        self.append(other)

        return self

    def __isub__(self, other):
        """Remove the given value from this MultiSelect."""

        if other not in self:
            raise ValueError(f"No such item: {other}")

        self.remove(other)

        return self

    def __contains__(self, name):
        """Determine if the given name is in this MultiSelect.

        To avoid confusion, only names are considered for comparison, not ID's.
        """

        for opt in self.multi_select:
            if opt.name == name:
                return True

        return False

    def __iter__(self):
        """Iterate over the SelectValue's in this property."""

        if self.multi_select is None:
            return None

        return iter(self.multi_select)

    @classmethod
    def __compose__(cls, *values):
        """Initialize a new MultiSelect from the given value(s)."""
        select = [SelectValue[value] for value in values if value is not None]

        return cls(multi_select=select)

    def append(self, *values):
        """Add selected values to this MultiSelect."""

        for value in values:
            if value is None:
                raise ValueError("'None' is an invalid value")

            if value not in self:
                self.multi_select.append(SelectValue[value])

    def remove(self, *values):
        """Remove selected values from this MultiSelect."""

        self.multi_select = [opt for opt in self.multi_select if opt.name not in values]

    @property
    def Values(self):
        """Return the names of each value in this MultiSelect as a list."""

        if self.multi_select is None:
            return None

        return [str(val) for val in self.multi_select if val.name is not None]


class People(PropertyValue, type="people"):
    """Notion people type."""

    people: List[User] = []

    def __iter__(self):
        """Iterate over the User's in this property."""

        if self.people is None:
            return None

        return iter(self.people)

    def __contains__(self, other):
        """Determine if the given User or name is in this People.

        To avoid confusion, only names are considered for comparison (not ID's).
        """

        for user in self.people:
            if user == other:
                return True

            if user.name == other:
                return True

        return False

    def __len__(self):
        """Return the number of People in this property."""

        return len(self.people)

    def __getitem__(self, index):
        """Return the People object at the given index."""

        if self.people is None:
            raise IndexError("empty property")

        if index > len(self.people):
            raise IndexError("index out of range")

        return self.people[index]

    def __str__(self):
        """Return a string representation of this property."""
        return ", ".join([str(user) for user in self.people])


class URL(NativeTypeMixin, PropertyValue, type="url"):
    """Notion URL type."""

    url: Optional[str] = None


class Email(NativeTypeMixin, PropertyValue, type="email"):
    """Notion email type."""

    email: Optional[str] = None


class PhoneNumber(NativeTypeMixin, PropertyValue, type="phone_number"):
    """Notion phone type."""

    phone_number: Optional[str] = None


class Files(PropertyValue, type="files"):
    """Notion files type."""

    files: List[FileObject] = []

    def __contains__(self, other):
        """Determine if the given FileObject or name is in the property."""

        if self.files is None:
            return False

        for ref in self.files:
            if ref == other:
                return True

            if ref.name == other:
                return True

        return False

    def __str__(self):
        """Return a string representation of this property."""
        return "; ".join([str(file) for file in self.files])

    def __iter__(self):
        """Iterate over the FileObject's in this property."""

        if self.files is None:
            return None

        return iter(self.files)

    def __len__(self):
        """Return the number of Files in this property."""

        return len(self.files)

    def __getitem__(self, name):
        """Return the FileObject with the given name."""

        if self.files is None:
            return None

        for ref in self.files:
            if ref.name == name:
                return ref

        raise AttributeError("No such file")

    def __iadd__(self, obj):
        """Append the given `FileObject` in place."""

        if obj in self:
            raise ValueError(f"Item exists: {obj}")

        self.append(obj)
        return self

    def __isub__(self, obj):
        """Remove the given `FileObject` in place."""

        if obj not in self:
            raise ValueError(f"No such item: {obj}")

        self.remove(obj)
        return self

    def append(self, obj):
        """Append the given file reference to this property.

        :param ref: the `FileObject` to be added
        """
        self.files.append(obj)

    def remove(self, obj):
        """Remove the given file reference from this property.

        :param ref: the `FileObject` to be removed
        """
        self.files.remove(obj)


class FormulaResult(TypedObject):
    """A Notion formula result.

    This object contains the result of the expression in the database properties.
    """

    def __str__(self):
        """Return the formula result as a string."""
        return self.Result or ""

    @property
    def Result(self):
        """Return the result of this FormulaResult."""
        raise NotImplementedError("Result unavailable")


class StringFormula(FormulaResult, type="string"):
    """A Notion string formula result."""

    string: Optional[str] = None

    @property
    def Result(self):
        """Return the result of this StringFormula."""
        return self.string


class NumberFormula(FormulaResult, type="number"):
    """A Notion number formula result."""

    number: Optional[Union[float, int]] = None

    @property
    def Result(self):
        """Return the result of this NumberFormula."""
        return self.number


class DateFormula(FormulaResult, type="date"):
    """A Notion date formula result."""

    date: Optional[DateRange] = None

    @property
    def Result(self):
        """Return the result of this DateFormula."""
        return self.date


class BooleanFormula(FormulaResult, type="boolean"):
    """A Notion boolean formula result."""

    boolean: Optional[bool] = None

    @property
    def Result(self):
        """Return the result of this BooleanFormula."""
        return self.boolean


class Formula(PropertyValue, type="formula"):
    """A Notion formula property value."""

    formula: Optional[FormulaResult] = None

    def __str__(self):
        """Return the result of this formula as a string."""
        return str(self.Result or "")

    @property
    def Result(self):
        """Return the result of this Formula in its native type."""

        if self.formula is None:
            return None

        return self.formula.Result


class Relation(PropertyValue, type="relation"):
    """A Notion relation property value."""

    relation: List[ObjectReference] = []
    has_more: bool = False

    @classmethod
    def __compose__(cls, *pages):
        """Return a `Relation` property with the specified pages."""
        return cls(relation=[ObjectReference[page] for page in pages])

    def __contains__(self, page):
        """Determine if the given page is in this Relation."""
        return ObjectReference[page] in self.relation

    def __iter__(self):
        """Iterate over the ObjectReference's in this property."""

        if self.relation is None:
            return None

        return iter(self.relation)

    def __len__(self):
        """Return the number of ObjectReference's in this property."""

        return len(self.relation)

    def __getitem__(self, index):
        """Return the ObjectReference object at the given index."""

        if self.relation is None:
            raise IndexError("empty property")

        if index > len(self.relation):
            raise IndexError("index out of range")

        return self.relation[index]

    def __iadd__(self, page):
        """Add the given page to this Relation in place."""

        ref = ObjectReference[page]

        if ref in self.relation:
            raise ValueError(f"Duplicate item: {ref.id}")

        self.relation.append(ref)

        return self

    def __isub__(self, page):
        """Remove the given page from this Relation in place."""

        ref = ObjectReference[page]

        if ref in self.relation:
            raise ValueError(f"No such item: {ref.id}")

        self.relation.remove(ref)

        return self


class RollupObject(TypedObject, ABC):
    """A Notion rollup property value."""

    function: Optional[Function] = None

    @property
    @abstractmethod
    def Value(self):
        """Return the native representation of this Rollup object."""


class RollupNumber(RollupObject, type="number"):
    """A Notion rollup number property value."""

    number: Optional[Union[float, int]] = None

    @property
    def Value(self):
        """Return the native representation of this Rollup object."""
        return self.number


class RollupDate(RollupObject, type="date"):
    """A Notion rollup date property value."""

    date: Optional[DateRange] = None

    @property
    def Value(self):
        """Return the native representation of this Rollup object."""
        return self.date


class RollupArray(RollupObject, type="array"):
    """A Notion rollup array property value."""

    array: List[PropertyValue]

    @property
    def Value(self):
        """Return the native representation of this Rollup object."""
        return self.array


class Rollup(PropertyValue, type="rollup"):
    """A Notion rollup property value."""

    rollup: Optional[RollupObject] = None

    def __str__(self):
        """Return a string representation of this Rollup property."""

        if self.rollup is None:
            return ""

        value = self.rollup.Value
        if value is None:
            return ""

        return str(value)


class CreatedTime(NativeTypeMixin, PropertyValue, type="created_time"):
    """A Notion created-time property value."""

    created_time: datetime


class CreatedBy(PropertyValue, type="created_by"):
    """A Notion created-by property value."""

    created_by: User

    def __str__(self):
        """Return the contents of this property as a string."""
        return str(self.created_by)


class LastEditedTime(NativeTypeMixin, PropertyValue, type="last_edited_time"):
    """A Notion last-edited-time property value."""

    last_edited_time: datetime


class LastEditedBy(PropertyValue, type="last_edited_by"):
    """A Notion last-edited-by property value."""

    last_edited_by: User

    def __str__(self):
        """Return the contents of this property as a string."""
        return str(self.last_edited_by)


# https://developers.notion.com/reference/property-item-object
class PropertyItem(PropertyValue, NotionObject, object="property_item"):
    """A `PropertyItem` returned by the Notion API.

    Basic property items have a similar schema to corresponding property values.  As a
    result, these items share the `PropertyValue` type definitions.

    This class provides a placeholder for parsing property items, however objects
    parse by this class will likely be `PropertyValue`'s instead.
    """

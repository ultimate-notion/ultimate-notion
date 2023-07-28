"""Wrapper for property values of pages"""
from abc import ABC, abstractmethod
from datetime import datetime

from ultimate_notion.obj_api import types
from ultimate_notion.obj_api.core import NotionObject
from ultimate_notion.obj_api.schema import Function
from ultimate_notion.obj_api.text import plain_text, rich_text, Color


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


class PropertyValue(types.TypedObject):
    """Base class for Notion property values."""

    id: str | None = None


class Title(NativeTypeMixin, PropertyValue, type="title"):
    """Notion title type."""

    title: list[types.RichTextObject] = []

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

    rich_text: list[types.RichTextObject] = []

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

    number: float | int | None = None

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

    checkbox: bool | None = None


class Date(PropertyValue, type="date"):
    """Notion complex date type - may include timestamp and/or be a date range."""

    date: types.DateRange | None = None

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
        return cls(date=types.DateRange(start=start, end=end))

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

    class _NestedData(types.GenericObject):
        name: str = None
        id: types.UUID | str | None = None
        color: Color | None = None

    status: _NestedData | None = None

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


class SelectValue(types.GenericObject):
    """Values for select & multi-select properties."""

    name: str
    id: types.UUID | str | None = None
    color: Color | None = None

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


class Select(NativeTypeMixin, PropertyValue, type="select"):
    """Notion select type."""

    select: SelectValue | None = None

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
        """Create a `Select` property from the given value.

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

    multi_select: list[SelectValue] = []

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

    people: list[types.User] = []

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

    url: str | None = None


class Email(NativeTypeMixin, PropertyValue, type="email"):
    """Notion email type."""

    email: str | None = None


class PhoneNumber(NativeTypeMixin, PropertyValue, type="phone_number"):
    """Notion phone type."""

    phone_number: str | None = None


class Files(PropertyValue, type="files"):
    """Notion files type."""

    files: list[types.FileObject] = []

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


class FormulaResult(types.TypedObject):
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

    string: str | None = None

    @property
    def Result(self):
        """Return the result of this StringFormula."""
        return self.string


class NumberFormula(FormulaResult, type="number"):
    """A Notion number formula result."""

    number: float | int | None = None

    @property
    def Result(self):
        """Return the result of this NumberFormula."""
        return self.number


class DateFormula(FormulaResult, type="date"):
    """A Notion date formula result."""

    date: types.DateRange | None = None

    @property
    def Result(self):
        """Return the result of this DateFormula."""
        return self.date


class BooleanFormula(FormulaResult, type="boolean"):
    """A Notion boolean formula result."""

    boolean: bool | None = None

    @property
    def Result(self):
        """Return the result of this BooleanFormula."""
        return self.boolean


class Formula(PropertyValue, type="formula"):
    """A Notion formula property value."""

    formula: FormulaResult | None = None

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

    relation: list[types.ObjectReference] = []
    has_more: bool = False

    @classmethod
    def __compose__(cls, *pages):
        """Return a `Relation` property with the specified pages."""
        return cls(relation=[types.ObjectReference[page] for page in pages])

    def __contains__(self, page):
        """Determine if the given page is in this Relation."""
        return types.ObjectReference[page] in self.relation

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

        ref = types.ObjectReference[page]

        if ref in self.relation:
            raise ValueError(f"Duplicate item: {ref.id}")

        self.relation.append(ref)

        return self

    def __isub__(self, page):
        """Remove the given page from this Relation in place."""

        ref = types.ObjectReference[page]

        if ref in self.relation:
            raise ValueError(f"No such item: {ref.id}")

        self.relation.remove(ref)

        return self


class RollupObject(types.TypedObject, ABC):
    """A Notion rollup property value."""

    function: Function | None = None

    @property
    @abstractmethod
    def Value(self):
        """Return the native representation of this Rollup object."""


class RollupNumber(RollupObject, type="number"):
    """A Notion rollup number property value."""

    number: float | int | None = None

    @property
    def Value(self):
        """Return the native representation of this Rollup object."""
        return self.number


class RollupDate(RollupObject, type="date"):
    """A Notion rollup date property value."""

    date: types.DateRange | None = None

    @property
    def Value(self):
        """Return the native representation of this Rollup object."""
        return self.date


class RollupArray(RollupObject, type="array"):
    """A Notion rollup array property value."""

    array: list[PropertyValue]

    @property
    def Value(self):
        """Return the native representation of this Rollup object."""
        return self.array


class Rollup(PropertyValue, type="rollup"):
    """A Notion rollup property value."""

    rollup: RollupObject | None = None

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

    created_by: types.User

    def __str__(self):
        """Return the contents of this property as a string."""
        return str(self.created_by)


class LastEditedTime(NativeTypeMixin, PropertyValue, type="last_edited_time"):
    """A Notion last-edited-time property value."""

    last_edited_time: datetime


class LastEditedBy(PropertyValue, type="last_edited_by"):
    """A Notion last-edited-by property value."""

    last_edited_by: types.User

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

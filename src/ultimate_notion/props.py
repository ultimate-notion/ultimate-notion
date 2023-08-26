"""
Page properties especially for pages within databases

The names of the properties reflect the name in the Notion UI.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar, Any, TYPE_CHECKING

import ultimate_notion.obj_api.props as obj_props
from ultimate_notion.objects import RichText, Option, User
from ultimate_notion.text import rich_text

if TYPE_CHECKING:
    from ultimate_notion.objects import File
    from ultimate_notion.page import Page

# Todo: Move the functionality from the PyDantic types in here


class PropertyValue:
    """Base class for Notion property values.

    Used to map high-level objects to low-level Notion-API objects
    """

    obj_ref: obj_props.PropertyValue
    readonly: bool = False  # value of property can not be set by us

    _param_type: ClassVar[type[RichText] | type[Option] | type[User] | None] = None
    _obj_api_map: ClassVar[dict[type[obj_props.PropertyValue], type[PropertyValue]]] = {}
    _type_value_map: ClassVar[dict[str, type[PropertyValue]]] = {}

    def __new__(cls, *args, **kwargs) -> PropertyValue:
        # Needed for wrap_obj_ref and its call to __new__ to work!
        return super().__new__(cls)

    def __init_subclass__(cls, type: type[obj_props.PropertyValue], **kwargs: Any):  # noqa: A002
        super().__init_subclass__(**kwargs)
        cls._obj_api_map[type] = cls
        cls._type_value_map[type.type] = cls

    @classmethod
    def wrap_obj_ref(cls, obj_ref: obj_props.PropertyValue) -> PropertyValue:
        prop_type_cls = cls._obj_api_map[type(obj_ref)]
        prop_type = prop_type_cls.__new__(prop_type_cls)
        prop_type.obj_ref = obj_ref
        return prop_type

    @property
    def _obj_api_map_inv(self) -> dict[type[PropertyValue], type[obj_props.PropertyValue]]:
        return {v: k for k, v in self._obj_api_map.items()}

    @property
    def _obj_api_type(self) -> type[obj_props.PropertyValue]:
        return self._obj_api_map_inv[self.__class__]

    def __init__(self, values):
        obj_api_type = self._obj_api_map_inv[self.__class__]
        if isinstance(values, list):
            values = [value.obj_ref if hasattr(value, "obj_ref") else value for value in values]
        else:
            values = values.obj_ref if hasattr(values, "obj_ref") else values

        self.obj_ref = obj_api_type.build(values)

    def __eq__(self, other: PropertyValue):
        return self.obj_ref.type == other.obj_ref.type and self.obj_ref() == self.obj_ref()

    # ToDo: Make this abstract and implement in every subclass -> Generics
    @property
    # @abstractmethod
    def value(self) -> Any:
        return self.obj_ref.value

    @property
    def id(self) -> str | None:
        return self.obj_ref.id


class Title(PropertyValue, type=obj_props.Title):
    """Title property value"""

    def __init__(self, text: str | RichText):
        if isinstance(text, str):
            text = rich_text(text)
        super().__init__(text)

    @property
    def value(self) -> str:
        return "".join(text.plain_text for text in self.obj_ref.value)


class Text(PropertyValue, type=obj_props.RichText):
    """Rich text property value"""

    def __init__(self, text: str | RichText):
        if isinstance(text, str):
            text = rich_text(text)
        super().__init__(text)


class Number(PropertyValue, type=obj_props.Number):
    """Simple number property value"""

    def __float__(self):
        """Return the Number as a `float`."""

        if self.obj_ref.number is None:
            raise ValueError("Cannot convert 'None' to float")

        return float(self.obj_ref.number)

    def __int__(self):
        """Return the Number as an `int`."""

        if self.obj_ref.number is None:
            raise ValueError("Cannot convert 'None' to int")

        return int(self.obj_ref.number)

    def __iadd__(self, other):
        """Add the given value to this Number."""

        if isinstance(other, Number):
            self.obj_ref.number += other.value
        else:
            self.obj_ref.number += other

        return self

    def __isub__(self, other):
        """Subtract the given value from this Number."""

        if isinstance(other, Number):
            self.obj_ref.number -= other.value
        else:
            self.obj_ref.number -= other

        return self

    def __imul__(self, other):
        """Multiply the given value from this Number."""

        if isinstance(other, Number):
            self.obj_ref.number *= other.value
        else:
            self.obj_ref.number *= other

        return self

    def __itruediv__(self, other):
        """Divide the given value from this Number."""

        if isinstance(other, Number):
            self.obj_ref.number /= other.value
        else:
            self.obj_ref.number /= other

        return self

    def __ifloordiv__(self, other):
        """Divide the given value from this Number and floor"""

        if isinstance(other, Number):
            self.obj_ref.number //= other.value
        else:
            self.obj_ref.number //= other

        return self

    def __add__(self, other):
        """Add the value of `other` and returns the result as a Number."""
        other_value = other.value if isinstance(other, Number) else other
        return Number(self.value + other_value)

    def __sub__(self, other):
        """Subtract the value of `other` and returns the result as a Number."""
        other_value = other.value if isinstance(other, Number) else other
        return Number(self.value - other_value)

    def __mul__(self, other):
        """Multiply the value of `other` and returns the result as a Number."""
        other_value = other.value if isinstance(other, Number) else other
        return Number(self.value * other_value)

    def __truediv__(self, other):
        other_value = other.value if isinstance(other, Number) else other
        return Number(self.value / other_value)

    def __floordiv__(self, other):
        other_value = other.value if isinstance(other, Number) else other
        return Number(self.value // other_value)

    def __le__(self, other):
        """Return `True` if this `Number` is less-than-or-equal-to `other`."""
        other_value = other.value if isinstance(other, Number) else other
        return self.value <= other_value

    def __lt__(self, other):
        """Return `True` if this `Number` is less-than `other`."""
        other_value = other.value if isinstance(other, Number) else other
        return self.value < other_value

    def __ge__(self, other):
        """Return `True` if this `Number` is greater-than-or-equal-to `other`."""
        other_value = other.value if isinstance(other, Number) else other
        return self.value >= other_value

    def __gt__(self, other):
        """Return `True` if this `Number` is greater-than `other`."""
        other_value = other.value if isinstance(other, Number) else other
        return self.value > other_value

    def __eq__(self, other):
        other_value = other.value if isinstance(other, Number) else other
        return self.value == other_value


class Checkbox(PropertyValue, type=obj_props.Checkbox):
    """Simple checkbox type; represented as a boolean."""


class Date(PropertyValue, type=obj_props.Date):
    """Date(-time) property value"""

    def __init__(self, start: datetime | date, end: datetime | date | None = None):
        self.obj_ref = obj_props.Date.build(start, end)

    @property
    def value(self) -> None | datetime | date | tuple[datetime | date, datetime | date]:
        date = self.obj_ref.date
        if date is None:
            return None
        elif date.end is None:
            return date.start
        else:
            return date.start, date.end


class Status(PropertyValue, type=obj_props.Status):
    """Status property value"""

    def __init__(self, option: str | Option):
        if isinstance(option, str):
            option = Option(option)

        super().__init__(option)

    @property
    def value(self) -> str:
        return self.obj_ref.status.name


class Select(PropertyValue, type=obj_props.Select):
    """Single select property value"""

    def __init__(self, option: str | Option):
        if isinstance(option, str):
            option = Option(option)

        super().__init__(option)


class MultiSelect(PropertyValue, type=obj_props.MultiSelect):
    """Notion multi-select type."""

    def __init__(self, options: str | Option | list[str] | list[Option]):
        if not isinstance(options, list):
            options = [options]
        options = [Option(option) if isinstance(option, str) else option for option in options]
        super().__init__(options)


class People(PropertyValue, type=obj_props.People):
    """Notion people type."""

    def __init__(self, users: User | list[User]):
        if not isinstance(users, list):
            users = [users]
        super().__init__(users)


class URL(PropertyValue, type=obj_props.URL):
    """Notion URL type."""


class Email(PropertyValue, type=obj_props.Email):
    """Notion email type."""


class PhoneNumber(PropertyValue, type=obj_props.PhoneNumber):
    """Notion phone type."""


class Files(PropertyValue, type=obj_props.Files):
    """Notion files type."""

    def __init__(self, files: File | list[File]):
        if not isinstance(files, list):
            files = [files]

        super().__init__(files)


class Formula(PropertyValue, type=obj_props.Formula):
    """A Notion formula property value."""

    readonly = True

    @property
    def value(self):
        return self.obj_ref.formula.value


class Relations(PropertyValue, type=obj_props.Relation):
    """A Notion relation property value."""

    def __init__(self, pages: Page | list[Page]):
        if not isinstance(pages, list):
            pages = [pages]
        super().__init__(pages)


class Rollup(PropertyValue, type=obj_props.Rollup):
    """A Notion rollup property value."""

    readonly = True

    @property
    def value(self):
        return self.obj_ref.rollup.value


class CreatedTime(PropertyValue, type=obj_props.CreatedTime):
    """A Notion created-time property value."""

    readonly = True


class CreatedBy(PropertyValue, type=obj_props.CreatedBy):
    """A Notion created-by property value."""

    readonly = True


class LastEditedTime(PropertyValue, type=obj_props.LastEditedTime):
    """A Notion last-edited-time property value."""

    readonly = True


class LastEditedBy(PropertyValue, type=obj_props.LastEditedBy):
    """A Notion last-edited-by property value."""

    readonly = True


class ID(PropertyValue, type=obj_props.UniqueID):
    """A Notion unique ID property value"""

    readonly = True


class Verification(PropertyValue, type=obj_props.Verification):
    """A verification property value of pages in wiki databases"""

    readonly = True
    # ToDo: Implement properties to retrieve user, etc. and convert user to actual high-level User object

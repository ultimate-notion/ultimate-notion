"""
Page properties especially for pages within databases

The names of the properties reflect the name in the Notion UI.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

import ultimate_notion.obj_api.props as obj_props
from ultimate_notion.objects import Option, RichText, User
from ultimate_notion.text import rich_text
from ultimate_notion.utils import Wrapper

if TYPE_CHECKING:
    from ultimate_notion.objects import File
    from ultimate_notion.page import Page

T = TypeVar('T', bound=obj_props.PropertyValue)


class PropertyValue(Wrapper[T], wraps=obj_props.PropertyValue):
    """Base class for Notion property values.

    Used to map high-level objects to low-level Notion-API objects
    """

    readonly: bool = False  # value of property can not be set by us
    _type_value_map: ClassVar[dict[str, type[PropertyValue]]] = {}

    def __init_subclass__(cls, wraps: type[T], **kwargs: Any):
        super().__init_subclass__(wraps=wraps, **kwargs)
        cls._type_value_map[wraps.type] = cls

    @property
    def _obj_api_type(self) -> type[obj_props.PropertyValue]:
        return self._obj_api_map_inv[self.__class__]

    def __init__(self, values):
        if isinstance(values, list):
            values = [value.obj_ref if isinstance(value, Wrapper) else value for value in values]
        else:
            values = values.obj_ref if isinstance(values, Wrapper) else values

        super().__init__(values)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PropertyValue):
            return NotImplemented
        return self.obj_ref.type == other.obj_ref.type and self.obj_ref.value == self.obj_ref.value

    # ToDo: Make this abstract and implement in every subclass -> Generics
    @property
    # @abstractmethod
    def value(self) -> Any:
        return self.obj_ref.value

    @property
    def id(self) -> str | None:  # noqa: A003
        return self.obj_ref.id


class Title(PropertyValue[obj_props.Title], wraps=obj_props.Title):
    """Title property value"""

    def __init__(self, text: str | RichText):
        if isinstance(text, str):
            text = rich_text(text)
        super().__init__(text)

    @property
    def value(self) -> str:
        return ''.join(text.plain_text for text in self.obj_ref.value)


class Text(PropertyValue[obj_props.RichText], wraps=obj_props.RichText):
    """Rich text property value"""

    def __init__(self, text: str | RichText):
        if isinstance(text, str):
            text = rich_text(text)
        super().__init__(text)


class Number(PropertyValue[obj_props.Number], wraps=obj_props.Number):
    """Simple number property value"""

    def __float__(self):
        """Return the Number as a `float`."""

        if self.obj_ref.number is None:
            msg = "Cannot convert 'None' to float"
            raise ValueError(msg)

        return float(self.obj_ref.number)

    def __int__(self):
        """Return the Number as an `int`."""

        if self.obj_ref.number is None:
            msg = "Cannot convert 'None' to int"
            raise ValueError(msg)

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


class Checkbox(PropertyValue[obj_props.Checkbox], wraps=obj_props.Checkbox):
    """Simple checkbox type; represented as a boolean."""


class Date(PropertyValue[obj_props.Date], wraps=obj_props.Date):
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


class Status(PropertyValue[obj_props.Status], wraps=obj_props.Status):
    """Status property value"""

    def __init__(self, option: str | Option):
        if isinstance(option, str):
            option = Option(option)

        super().__init__(option)

    @property
    def value(self) -> str | None:
        if self.obj_ref.status:
            return self.obj_ref.status.name
        else:
            return None


class Select(PropertyValue[obj_props.Select], wraps=obj_props.Select):
    """Single select property value"""

    def __init__(self, option: str | Option):
        if isinstance(option, str):
            option = Option(option)

        super().__init__(option)


class MultiSelect(PropertyValue[obj_props.MultiSelect], wraps=obj_props.MultiSelect):
    """Notion multi-select type."""

    def __init__(self, options: str | Option | list[str | Option]):
        if not isinstance(options, list):
            options = [options]
        options = [Option(option) if isinstance(option, str) else option for option in options]
        super().__init__(options)


class People(PropertyValue[obj_props.People], wraps=obj_props.People):
    """Notion people type."""

    def __init__(self, users: User | list[User]):
        if not isinstance(users, list):
            users = [users]
        super().__init__(users)


class URL(PropertyValue[obj_props.URL], wraps=obj_props.URL):
    """Notion URL type."""


class Email(PropertyValue[obj_props.Email], wraps=obj_props.Email):
    """Notion email type."""


class PhoneNumber(PropertyValue[obj_props.PhoneNumber], wraps=obj_props.PhoneNumber):
    """Notion phone type."""


class Files(PropertyValue[obj_props.Files], wraps=obj_props.Files):
    """Notion files type."""

    def __init__(self, files: File | list[File]):
        if not isinstance(files, list):
            files = [files]

        super().__init__(files)


class Formula(PropertyValue[obj_props.Formula], wraps=obj_props.Formula):
    """A Notion formula property value."""

    readonly = True

    @property
    def value(self):
        return self.obj_ref.formula.value


class Relations(PropertyValue[obj_props.Relation], wraps=obj_props.Relation):
    """A Notion relation property value."""

    def __init__(self, pages: Page | list[Page]):
        if not isinstance(pages, list):
            pages = [pages]
        super().__init__(pages)


class Rollup(PropertyValue[obj_props.Rollup], wraps=obj_props.Rollup):
    """A Notion rollup property value."""

    readonly = True

    @property
    def value(self):
        return self.obj_ref.rollup.value


class CreatedTime(PropertyValue[obj_props.CreatedTime], wraps=obj_props.CreatedTime):
    """A Notion created-time property value."""

    readonly = True


class CreatedBy(PropertyValue[obj_props.CreatedBy], wraps=obj_props.CreatedBy):
    """A Notion created-by property value."""

    readonly = True


class LastEditedTime(PropertyValue[obj_props.LastEditedTime], wraps=obj_props.LastEditedTime):
    """A Notion last-edited-time property value."""

    readonly = True


class LastEditedBy(PropertyValue[obj_props.LastEditedBy], wraps=obj_props.LastEditedBy):
    """A Notion last-edited-by property value."""

    readonly = True


class ID(PropertyValue[obj_props.UniqueID], wraps=obj_props.UniqueID):
    """A Notion unique ID property value"""

    readonly = True


class Verification(PropertyValue[obj_props.Verification], wraps=obj_props.Verification):
    """A verification property value of pages in wiki databases"""

    readonly = True
    # ToDo: Implement properties to retrieve user, etc. and convert user to actual high-level User object

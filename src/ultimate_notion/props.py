"""
Page property values especially for pages within databases.
The names of the properties reflect the name in the Notion UI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, ClassVar, cast

import pendulum as pnd
from typing_extensions import Self, TypeVar

import ultimate_notion.obj_api.props as obj_props
from ultimate_notion import rich_text as rt
from ultimate_notion.core import Wrapper, get_active_session, get_repr, raise_unset
from ultimate_notion.file import AnyFile
from ultimate_notion.obj_api.enums import FormulaType, RollupType, VState
from ultimate_notion.obj_api.objects import DateRange, DateTimeOrRange
from ultimate_notion.option import Option
from ultimate_notion.user import User

if TYPE_CHECKING:
    from ultimate_notion.page import Page

PV_co = TypeVar('PV_co', bound=obj_props.PropertyValue, default=obj_props.PropertyValue, covariant=True)


class PropertyValue(Wrapper[PV_co], ABC, wraps=obj_props.PropertyValue):  # noqa: PLW1641
    """Base class for Notion property values.

    Used to map high-level objects to low-level Notion-API objects
    """

    readonly: bool = False  # value of property can not be set by us
    _type_value_map: ClassVar[dict[str, type[PropertyValue]]] = {}

    def __init_subclass__(cls, wraps: type[PV_co], **kwargs: Any):
        super().__init_subclass__(wraps=wraps, **kwargs)
        # When this is called, the model is not yet constructed, thus no direct field access with .type.
        type_name = wraps.model_fields['type'].get_default()
        cls._type_value_map[type_name] = cls

    @property
    def _obj_api_type(self) -> type[obj_props.PropertyValue]:
        return self._obj_api_map_inv[self.__class__]

    def __init__(self, values: Any | Sequence[Any]):
        if isinstance(values, Sequence) and not isinstance(values, str | bytes):
            values = [value.obj_ref if isinstance(value, Wrapper) else value for value in values]
        else:
            values = values.obj_ref if isinstance(values, Wrapper) else values

        super().__init__(values)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PropertyValue):
            return NotImplemented
        other_obj_ref = cast(PV_co, other.obj_ref)
        return (self.obj_ref.type == other_obj_ref.type) and (self.obj_ref.value == other_obj_ref.value)

    @property
    @abstractmethod
    def value(self) -> Any:
        """Return the actual Python value object of this property."""

    @property
    def id(self) -> str:
        return raise_unset(self.obj_ref.id)

    def __repr__(self) -> str:
        return get_repr(self)

    def __str__(self) -> str:
        if isinstance(self.value, rt.Text):
            return str(self.value) if self.value else ''
        elif isinstance(self.value, list):
            # workaround as `str` on lists calls `repr` instead of `str`
            return ', '.join(str(val) for val in self.value)
        else:
            return str(self.value) if self.value else ''


#############################
# Writeable Property Values #
#############################


class Title(PropertyValue[obj_props.Title], wraps=obj_props.Title):
    """Title property value."""

    def __init__(self, text: str):
        super().__init__(rt.Text(text).obj_ref)

    @property
    def value(self) -> rt.Text:
        return rt.Text.wrap_obj_ref(self.obj_ref.title)


class Text(PropertyValue[obj_props.RichText], wraps=obj_props.RichText):
    """Rich text property value."""

    def __init__(self, text: str):
        super().__init__(rt.Text(text).obj_ref)

    @property
    def value(self) -> rt.Text:
        return rt.Text.wrap_obj_ref(self.obj_ref.rich_text)


class Number(PropertyValue[obj_props.Number], wraps=obj_props.Number):
    """Number property value."""

    @property
    def value(self) -> int | float | None:
        return self.obj_ref.number


class Checkbox(PropertyValue[obj_props.Checkbox], wraps=obj_props.Checkbox):
    """Simple checkbox type; represented as a boolean."""

    @property
    def value(self) -> bool | None:
        return self.obj_ref.checkbox


class Date(PropertyValue[obj_props.Date], wraps=obj_props.Date):
    """Date(-time) property value."""

    def __init__(self, dt_spec: str | DateTimeOrRange):
        self.obj_ref = obj_props.Date.build(dt_spec)

    @property
    def value(self) -> DateTimeOrRange | None:
        date = self.obj_ref.date
        if date is None:
            return None
        else:
            return date.to_pendulum()


class Status(PropertyValue[obj_props.Status], wraps=obj_props.Status):
    """Status property value."""

    def __init__(self, option: str | Option):
        if isinstance(option, str):
            option = Option(option)

        super().__init__(option)

    @property
    def value(self) -> Option | None:
        if self.obj_ref.status:
            return Option.wrap_obj_ref(self.obj_ref.status)
        else:
            return None


class Select(PropertyValue[obj_props.Select], wraps=obj_props.Select):
    """Single select property value."""

    def __init__(self, option: str | Option):
        if isinstance(option, str):
            option = Option(option)

        super().__init__(option)

    @property
    def value(self) -> Option | None:
        if self.obj_ref.select:
            return Option.wrap_obj_ref(self.obj_ref.select)
        else:
            return None


class MultiSelect(PropertyValue[obj_props.MultiSelect], wraps=obj_props.MultiSelect):
    """Multi-select property value."""

    def __init__(self, options: str | Option | Sequence[str | Option]):
        if not isinstance(options, Sequence | str) or isinstance(options, str):
            options = [options]
        options = [Option(option) if isinstance(option, str) else option for option in options]
        super().__init__(options)

    @property
    def value(self) -> list[Option] | None:
        if self.obj_ref.multi_select:
            return [Option.wrap_obj_ref(option) for option in self.obj_ref.multi_select]
        else:
            return None


class Person(PropertyValue[obj_props.People], wraps=obj_props.People):
    """Person/People property value."""

    def __init__(self, users: User | Sequence[User]):
        if not isinstance(users, Sequence):
            users = [users]
        super().__init__(users)

    @property
    def value(self) -> list[User]:
        session = get_active_session()
        return [session.get_user(user.id, raise_on_unknown=False) for user in self.obj_ref.people]


class URL(PropertyValue[obj_props.URL], wraps=obj_props.URL):
    """URL property value."""

    @property
    def value(self) -> str | None:
        return self.obj_ref.url


class Email(PropertyValue[obj_props.Email], wraps=obj_props.Email):
    """Email property value."""

    @property
    def value(self) -> str | None:
        return self.obj_ref.email


class Phone(PropertyValue[obj_props.PhoneNumber], wraps=obj_props.PhoneNumber):
    """Phone property value."""

    @property
    def value(self) -> str | None:
        return self.obj_ref.phone_number


class Files(PropertyValue[obj_props.Files], wraps=obj_props.Files):
    """Files property value."""

    def __init__(self, files: AnyFile | Sequence[AnyFile]):
        if not isinstance(files, Sequence):
            files = [files]

        super().__init__(files)

    @property
    def value(self) -> list[AnyFile]:
        return [AnyFile.wrap_obj_ref(file) for file in self.obj_ref.files]


class Relations(PropertyValue[obj_props.Relation], wraps=obj_props.Relation):
    """Relation property values."""

    def __init__(self, pages: Page | Sequence[Page]):
        if not isinstance(pages, Sequence):
            pages = [pages]
        super().__init__(pages)

    @property
    def value(self) -> list[Page]:
        session = get_active_session()
        return [session.get_page(ref_obj.id) for ref_obj in self.obj_ref.relation]


#############################
# Read-Only Property Values #
#############################


class Formula(PropertyValue[obj_props.Formula], wraps=obj_props.Formula):
    """Formula property value."""

    readonly = True

    @property
    def value(self) -> str | float | int | DateTimeOrRange | None:
        """Return the result value of the formula."""
        # returns all values of subclasses of `FormulaResult`
        if self.obj_ref.formula is None:
            return None
        match value := self.obj_ref.formula.value:
            case DateRange():
                return value.to_pendulum() if value else None
            case str() | int() | float():
                return value
            case _:
                return None

    @property
    def value_type(self) -> FormulaType | None:
        """Return the type of the formula result."""
        return FormulaType(self.obj_ref.formula.type) if self.obj_ref.formula else None


class Rollup(PropertyValue[obj_props.Rollup], wraps=obj_props.Rollup):
    """Rollup property value."""

    readonly = True

    @property
    def value(self) -> float | int | DateTimeOrRange | list[Any] | None:
        """Return the result value of the rollup."""
        match rollup_type := self.obj_ref.rollup:
            case None:
                return None
            case obj_props.RollupArray():
                return [PropertyValue.wrap_obj_ref(prop).value for prop in rollup_type.array]
            case obj_props.RollupNumber():
                return rollup_type.number
            case obj_props.RollupDate():
                return rollup_type.date.to_pendulum() if rollup_type.date is not None else None
            case _:
                msg = f'Unknown rollup value type: {type(rollup_type)}'
                raise ValueError(msg)

    @property
    def value_type(self) -> RollupType | None:
        """Return the type of the rollup result."""
        return RollupType(self.obj_ref.rollup.type) if self.obj_ref.rollup else None


class CreatedTime(PropertyValue[obj_props.CreatedTime], wraps=obj_props.CreatedTime):
    """Created-time property value."""

    readonly = True

    @property
    def value(self) -> pnd.DateTime:
        return pnd.instance(self.obj_ref.created_time)


class CreatedBy(PropertyValue[obj_props.CreatedBy], wraps=obj_props.CreatedBy):
    """Created-by property value."""

    readonly = True

    @property
    def value(self) -> User:
        session = get_active_session()
        return session.get_user(self.obj_ref.created_by.id, raise_on_unknown=False)


class LastEditedTime(PropertyValue[obj_props.LastEditedTime], wraps=obj_props.LastEditedTime):
    """Last-edited-time property value."""

    readonly = True

    @property
    def value(self) -> pnd.DateTime:
        return pnd.instance(self.obj_ref.last_edited_time)


class LastEditedBy(PropertyValue[obj_props.LastEditedBy], wraps=obj_props.LastEditedBy):
    """Last-edited-by property value."""

    readonly = True

    @property
    def value(self) -> User:
        session = get_active_session()
        return session.get_user(self.obj_ref.last_edited_by.id, raise_on_unknown=False)


class ID(PropertyValue[obj_props.UniqueID], wraps=obj_props.UniqueID):
    """Unique ID property value."""

    readonly = True

    @property
    def number(self) -> int:
        return self.obj_ref.unique_id.number

    @property
    def prefix(self) -> str | None:
        return self.obj_ref.unique_id.prefix

    @property
    def value(self) -> str:
        return f'{self.prefix}-{self.number}'


class Verification(PropertyValue[obj_props.Verification], wraps=obj_props.Verification):
    """Verification property value of pages in wiki databases."""

    # ToDo: Write a unit test for this!
    readonly = True

    @property
    def value(self) -> Self:
        return self

    @property
    def state(self) -> VState:
        return self.obj_ref.verification.state

    @property
    def verified_by(self) -> User | None:
        if self.obj_ref.verification.verified_by is None:
            return None
        else:
            session = get_active_session()
            return session.get_user(self.obj_ref.verification.verified_by.id, raise_on_unknown=False)

    @property
    def date(self) -> pnd.DateTime | None:
        if self.obj_ref.verification.date is None:
            return None
        else:
            return pnd.instance(self.obj_ref.verification.date)


class Button(PropertyValue[obj_props.Button], wraps=obj_props.Button):
    """Button property value.

    This is a read-only property that represents a button in a database.
    """

    readonly = True

    @property
    def value(self) -> None:
        return None

    def __str__(self) -> str:
        return f'Button(id={self.id})'

    def __repr__(self) -> str:
        return get_repr(self, desc=self.id)

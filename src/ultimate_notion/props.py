"""
Page properties especially for pages within databases

The names of the properties reflect the name in the Notion UI.
"""
from __future__ import annotations

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
    _has_compose: ClassVar[dict[type[obj_props.PropertyValue], bool]] = {}

    def __new__(cls, *args, **kwargs) -> PropertyValue:
        # Needed for wrap_obj_ref and its call to __new__ to work!
        return super().__new__(cls)

    def __init_subclass__(cls, type: type[obj_props.PropertyValue], **kwargs: Any):  # noqa: A002
        super().__init_subclass__(**kwargs)
        cls._obj_api_map[type] = cls
        cls._has_compose[type] = hasattr(type, '__compose__')
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


class Checkbox(PropertyValue, type=obj_props.Checkbox):
    """Simple checkbox type; represented as a boolean."""


class Date(PropertyValue, type=obj_props.Date):
    """Date(-time) property value"""


class Status(PropertyValue, type=obj_props.Status):
    """Status property value"""

    def __init__(self, option: str | Option):
        if isinstance(option, str):
            option = Option(option)

        super().__init__(option)


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


class Relations(PropertyValue, type=obj_props.Relation):
    """A Notion relation property value."""

    def __init__(self, pages: Page | list[Page]):
        if not isinstance(pages, list):
            pages = [pages]
        super().__init__(pages)


class Rollup(PropertyValue, type=obj_props.Rollup):
    """A Notion rollup property value."""

    readonly = True


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

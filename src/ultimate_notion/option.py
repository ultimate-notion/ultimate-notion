"""Functionality for general Notion objects like texts, files, options, etc."""

from __future__ import annotations

from ultimate_notion.core import Wrapper, get_repr
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.core import Unset, UnsetType, raise_unset
from ultimate_notion.obj_api.enums import Color
from ultimate_notion.rich_text import Text


class Option(Wrapper[objs.SelectOption], wraps=objs.SelectOption):
    """Option for select & multi-select property."""

    def __init__(self, name: str, *, color: Color | str | UnsetType = Unset) -> None:
        if isinstance(color, str):
            color = Color(color)
        super().__init__(name, color=color)

    def __repr__(self) -> str:
        return get_repr(self)

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Option):
            res = self.obj_ref == other.obj_ref
        elif isinstance(other, str):
            res = self.name == other
        elif other is None:
            res = False
        else:
            msg = f'Cannot compare Option with types {type(other)}'
            raise RuntimeError(msg)
        return res

    def __hash__(self) -> int:
        return super().__hash__()

    @property
    def id(self) -> str:
        """ID of the option."""
        return raise_unset(self.obj_ref.id)

    @property
    def name(self) -> str:
        """Name of the option."""
        return self.obj_ref.name

    @property
    def color(self) -> Color:
        """Color of the option."""
        try:
            return raise_unset(self.obj_ref.color)
        except ValueError:  # i.e. unset value
            return Color.DEFAULT

    @property
    def description(self) -> str:
        """Description of the option."""
        if desc := self.obj_ref.description:
            return Text.wrap_obj_ref(desc)
        else:
            return ''


class OptionNSType(type):
    """Metaclass to implement `len` for type `OptionNS` itself, not an instance of it."""

    # ToDo: When mypy is smart enough to understand metaclasses, we can remove the `type: ignore` comments.

    def __len__(cls: type[OptionNS]) -> int:  # type: ignore[misc]
        return len(cls.to_list())


class OptionNS(metaclass=OptionNSType):
    """Option namespace to simplify working with (Multi-)Select options."""

    @classmethod
    def to_list(cls) -> list[Option]:
        """Convert the enum to a list as needed by the (Multi)Select property types."""
        return [
            getattr(cls, var) for var in cls.__dict__ if not var.startswith('__') and not callable(getattr(cls, var))
        ]


class OptionGroup(Wrapper[objs.SelectGroup], wraps=objs.SelectGroup):
    """Group of options for status property."""

    _options: dict[str, Option]  # holds all possible options

    @classmethod
    def wrap_obj_ref(cls, obj_ref: objs.SelectGroup, /, *, options: list[Option] | None = None) -> OptionGroup:
        """Convienence constructor for the group of options."""
        obj = super().wrap_obj_ref(obj_ref)
        options = [] if options is None else options
        obj._options = {option.id: option for option in options}
        return obj

    @property
    def name(self) -> str:
        """Name of the option group."""
        return self.obj_ref.name

    @property
    def options(self) -> list[Option]:
        """Options within this option group."""
        return [self._options[opt_id] for opt_id in self.obj_ref.option_ids]

    def __repr__(self) -> str:
        return get_repr(self)

    def __str__(self) -> str:
        return self.name


def check_for_updates(old: list[Option], new: list[Option]) -> dict[str, list[str]]:
    """Check if two lists of options contain updates.

    Returns which attributes have changed for each option. This is mainly used to check if options have changed
    when updating a select or multi-select property as this is not supported by the Notion API.
    """
    old_by_name = {opt.name: opt for opt in old}
    new_by_name = {opt.name: opt for opt in new}
    common_names = set(old_by_name) & set(new_by_name)

    updates: dict[str, list[str]] = {}
    for name in common_names:
        old_opt = old_by_name[name]
        new_opt = new_by_name[name]

        for attr in ('name', 'color', 'description'):
            if getattr(old_opt, attr) != getattr(new_opt, attr):
                updates.setdefault(name, []).append(attr)
    return updates

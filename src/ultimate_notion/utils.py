"""Additional utilities that fit nowhere else."""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Callable, Generator, Iterator, Mapping, Sequence
from contextlib import contextmanager
from hashlib import sha256
from typing import Any, TypeAlias, TypeVar

import numpy as np
import pendulum as pnd
import tomli_w
from numpy.typing import NDArray
from packaging.version import Version
from pendulum.tz import local_timezone
from pydantic import BaseModel

from ultimate_notion import __version__
from ultimate_notion.errors import EmptyListError, MultipleItemsError

T = TypeVar('T')  # ToDo: Use new syntax when requires-python >= 3.12


class SList(list[T]):
    """A list that holds often only a single element."""

    def item(self) -> T:
        if len(self) == 1:
            return self[0]
        elif len(self) == 0:
            msg = 'list is empty'
            raise EmptyListError(msg)
        else:
            msg = 'list has multiple items'
            raise MultipleItemsError(msg)


def safe_list_get(lst: Sequence[T], idx: int, *, default: T | None = None) -> T | None:
    """Get the element at the index of the list or return the default value."""
    try:
        return lst[idx]
    except IndexError:
        return default


def is_notebook() -> bool:
    """Determine if we are running within a Jupyter notebook."""
    try:
        from IPython.core.getipython import get_ipython  # noqa: PLC0415
    except ModuleNotFoundError:
        return False  # Probably standard Python interpreter
    else:
        shell = get_ipython().__class__.__name__  # type: ignore[no-untyped-call]
        if shell == 'ZMQInteractiveShell':
            return True  # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)


def display_html(html: str, *, raw: bool = False) -> None:
    """Render HTML in the active Jupyter frontend.

    Wraps IPython's untyped ``display_html`` so its missing annotations stay
    contained at this single boundary instead of leaking to every call site.
    """
    from IPython.display import display_html as ipy_display_html  # noqa: PLC0415

    render: Callable[..., None] = ipy_display_html
    render(html, raw=raw)


def display_markdown(markdown: str, *, raw: bool = False) -> None:
    """Render Markdown in the active Jupyter frontend.

    Wraps IPython's untyped ``display_markdown`` so its missing annotations stay
    contained at this single boundary instead of leaking to every call site.
    """
    from IPython.core.display import display_markdown as ipy_display_markdown  # noqa: PLC0415

    render: Callable[..., None] = ipy_display_markdown
    render(markdown, raw=raw)


def find_indices(
    elements: NDArray[np.int_] | Sequence[Any], total_set: NDArray[np.int_] | Sequence[Any]
) -> NDArray[np.int_]:
    """Finds the indices of the elements in the total set."""
    total_arr = np.asarray(total_set)
    mask = np.isin(total_arr, elements)
    indices = np.where(mask)[0]
    lookup = dict(zip(total_arr[mask], indices, strict=True))
    result = np.array([lookup.get(x) for x in elements])
    return result


def find_index(elem: Any, lst: list[Any]) -> int | None:
    """Find the index of the element in the list or return `None`."""
    try:
        return lst.index(elem)
    except ValueError:
        return None


KT = TypeVar('KT')  # ToDo: Use new syntax when requires-python >= 3.12
VT = TypeVar('VT')  # ToDo: Use new syntax when requires-python >= 3.12


def dict_diff(dct1: Mapping[KT, VT], dct2: Mapping[KT, VT]) -> tuple[list[KT], list[KT], dict[KT, tuple[VT, VT]]]:
    """Returns the added keys, removed keys and keys of changed values of both dictionaries."""
    set1, set2 = set(dct1.keys()), set(dct2.keys())
    keys_added = list(set2 - set1)
    keys_removed = list(set1 - set2)
    values_changed = {key: (dct1[key], dct2[key]) for key in set1 & set2 if dct1[key] != dct2[key]}
    return keys_added, keys_removed, values_changed


def dict_diff_str(dct1: Mapping[KT, VT], dct2: Mapping[KT, VT]) -> tuple[list[str], list[str], list[str]]:
    """Returns the added keys, removed keys and keys of changed values of both dictionaries."""
    keys_added, keys_removed, values_changed = dict_diff(dct1, dct2)
    keys_added_str = [str(k) for k in keys_added]
    keys_removed_str = [str(k) for k in keys_removed]
    keys_changed_str = [f'{k}: {v[0]} -> {v[1]}' for k, v in values_changed.items()]
    return keys_added_str, keys_removed_str, keys_changed_str


def str_hash(*args: str, n_chars: int = 16) -> str:
    """Hashes string arguments to a n-character string."""
    return sha256(''.join(args).encode('utf-8')).hexdigest()[:n_chars]


def rank(arr: NDArray[np.int_]) -> NDArray[np.int_]:
    """Returns the rank of the elements in the array and gives the same rank to equal elements."""
    mask = np.argsort(arr)
    rank = np.zeros_like(arr)
    rank[1:] = np.cumsum(np.where(np.diff(arr[mask]) != 0, 1, 0))
    return rank[np.argsort(mask)]


def is_stable_version(version_str: str) -> bool:
    """Return whether the given version is a stable release."""
    version = Version(version_str)
    return not (version.is_prerelease or version.is_devrelease or version.is_postrelease)


def is_stable_release() -> bool:
    """Return whether the current version is a stable release."""
    return is_stable_version(__version__)


DateTimeOrRange: TypeAlias = dt.datetime | dt.date | pnd.Interval[pnd.DateTime] | pnd.Interval[pnd.Date]
"""A type alias for various date, date time and interval representations."""


def parse_dt_str(dt_str: str) -> DateTimeOrRange:
    """Parse typical Notion date/datetime/interval strings to pendulum objects.

    If no timezone is provided assume local timezone and convert everything else to UTC for consistency."""

    def set_tz(dt_spec: pnd.DateTime | pnd.Date | dt.datetime | dt.date) -> pnd.DateTime | pnd.Date:
        """Set the timezone of the datetime specifier object if necessary."""
        match dt_spec:
            case pnd.DateTime() if dt_spec.tz is None:
                return dt_spec.in_tz('local')
            case pnd.DateTime():
                return dt_spec.in_tz('UTC')  # to avoid unnamed timezones we convert to UTC
            case pnd.Date():
                return dt_spec  # as it is a date and has no tz information
            case _:
                msg = f'Unexpected type `{type(dt_spec)}` for `{dt_spec}`'
                raise TypeError(msg)

    # Handle strings with "Europe/Berlin" and "UTC" style timezone
    if match := re.match(r'(.+)\s+([A-Za-z/]+)$', dt_str.strip()):
        dt_part, tz_part = match.groups()
        dt_spec = pnd.parse(dt_part, exact=True, tz=None)
        match dt_spec:
            case pnd.DateTime():
                dt_spec = dt_spec.in_tz(tz_part)
            case _:
                msg = f'Expected a datetime string but got {dt_str}'
                raise ValueError(msg)
    else:
        dt_spec = pnd.parse(dt_str, exact=True, tz=None)

    match dt_spec:
        case pnd.DateTime():
            return set_tz(dt_spec)
        case pnd.Date():
            return dt_spec
        case pnd.Interval(start=pnd.Date() as raw_start, end=pnd.Date() as raw_end):
            # We extend the interval to the full day if only a date is given
            start, end = set_tz(raw_start), set_tz(raw_end)
            if not isinstance(raw_start, pnd.DateTime):
                start = pnd.datetime(start.year, start.month, start.day, 0, 0, 0)
            if not isinstance(raw_end, pnd.DateTime):
                end = pnd.datetime(end.year, end.month, end.day, 23, 59, 59)
            return pnd.Interval(start=start, end=end)
        case _:
            msg = f'Unexpected parsing result of type {type(dt_spec)} for {dt_str}'
            raise TypeError(msg)


def to_pendulum(dt_spec: str | DateTimeOrRange) -> DateTimeOrRange:
    """Convert a datetime or date object to a pendulum object."""
    match dt_spec:
        case pnd.DateTime() | pnd.Date() | pnd.Interval():
            return dt_spec
        case str():
            return parse_dt_str(dt_spec)
        case dt.datetime() if dt_spec.tzinfo is None:
            return pnd.instance(dt_spec, tz='local')
        case dt.datetime():
            return pnd.instance(dt_spec).in_tz('UTC')  # to avoid unnamed timezones we convert to UTC
        case dt.date():
            return pnd.instance(dt_spec)
        case _:
            msg = f'Unexpected type {type(dt_spec)} for {dt_spec}'
            raise TypeError(msg)


@contextmanager
def temp_timezone(tz: str | pnd.Timezone) -> Iterator[None]:
    """Temporarily set the local timezone to the given timezone. Mostly used by unit tests."""
    if not isinstance(tz, pnd.Timezone):
        tz = pnd.timezone(tz)

    current_tz = local_timezone()
    if not isinstance(current_tz, pnd.Timezone):
        msg = f'Expected a Timezone object but got type {type(current_tz)}.'
        raise RuntimeError(msg)
    pnd.set_local_timezone(tz)
    try:
        yield
    finally:
        pnd.set_local_timezone(current_tz)


PT = TypeVar('PT', bound=BaseModel)  # ToDo: Use new syntax when requires-python >= 3.12


def set_attr_none(
    obj: PT, attr_paths: str | Sequence[str] | None, *, inplace: bool = False, missing_ok: bool = False
) -> PT:
    """Set the attributes given by a potentially nested path to None.

    `None` attributes will be removed during serialization by default.
    """
    if attr_paths is None:
        return obj
    if isinstance(attr_paths, str):
        attr_paths = [attr_paths]

    if not inplace:
        obj = obj.model_copy(deep=True)
    for attr_path in attr_paths:
        attrs = attr_path.split('.')

        curr_obj: Any = obj
        for lvl, attr in enumerate(attrs[:-1]):
            curr_obj = getattr(curr_obj, attr, None)
            if curr_obj is None and not missing_ok:
                msg = f'{attr} does not exist in {".".join(attrs[: lvl - 1]) if lvl > 1 else "the object"}.'
                raise AttributeError(msg)

        last_attr = attrs[-1]
        if hasattr(curr_obj, last_attr):
            setattr(curr_obj, last_attr, None)
        elif not missing_ok:
            msg = f'{last_attr} does not exist in {".".join(attrs[:-2]) if len(attrs) > 1 else "the object"}.'
            raise AttributeError(msg)

    return obj


@contextmanager
def temp_attr(obj: object, **kwargs: Any) -> Generator[None, None, None]:
    """
    Temporarily sets multiple attributes of an object to specified values,
    and restores their original values after the context exits.

    Args:
        obj (object): The object whose attributes will be modified.
        **kwargs (Any): The attributes and their temporary values to modify.
    """
    orig_values = {attr: getattr(obj, attr, None) for attr in kwargs}
    for attr, new_value in kwargs.items():
        setattr(obj, attr, new_value)
    try:
        yield
    finally:
        for attr, original_value in orig_values.items():
            setattr(obj, attr, original_value)


def rec_apply(func: Callable[[Any], Any], obj: Any) -> Any:
    """
    Recursively applies a function `func` to all elements in a nested structure.

    - Applies `func` to every non-container element.
    - Recurses into lists, tuples and dicts.
    - Strings are treated as atomic elements and are **not** considered containers.

    Example:
        rows = [[1, 2], [3, [4, 5]]]
        result = recursive_apply(rows, lambda x: x * 2)
        print(result)  # [[2, 4], [6, [8, 10]]]
    """
    if isinstance(obj, str):  # str is a sequence!
        return func(obj)
    elif isinstance(obj, Sequence):
        return [rec_apply(func, item) for item in obj]
    elif isinstance(obj, Mapping):
        return {k: rec_apply(func, v) for k, v in obj.items()}
    else:
        return func(obj)


def pydantic_to_toml(model: BaseModel) -> str:
    """Convert a Pydantic model to a TOML string."""
    json_dct = json.loads(model.model_dump_json())
    # Remove None as TOML doesn't support null/None values.
    json_dct = rec_apply(lambda x: '' if x is None else x, json_dct)
    return tomli_w.dumps(json_dct)


def pydantic_apply(obj: PT, func: Callable[[Any, Any], Any]) -> PT:
    """Apply a function to all fields, i.e. (name, value), of a Pydantic model recursively.

    The transformed model is returned as a copy, leaving the original model unchanged.
    """

    def _trans_list_elem(name: str, elem: Any) -> Any:
        if isinstance(elem, BaseModel):
            return pydantic_apply(elem, func)
        elif isinstance(elem, list):  # happens for cells of a TableRow
            return [pydantic_apply(item, func) for item in elem]
        else:
            return func(name, elem)

    upd_obj = obj.model_copy(deep=True)
    for name in upd_obj.__class__.model_fields:
        value = getattr(upd_obj, name)
        if isinstance(value, BaseModel):  # First dive into nested BaseModels ...
            setattr(upd_obj, name, value := pydantic_apply(value, func))
        # ... then work on the key-value pairs directly, where := updates value to remove, e.g. empty lists
        setattr(upd_obj, name, value := func(name, value))

        if isinstance(value, list):
            new_list = [_trans_list_elem(name, item) for item in value]
            setattr(upd_obj, name, new_list)
        elif isinstance(value, dict):
            new_dict = {
                k: pydantic_apply(v, func) if isinstance(v, BaseModel) else func(name, v) for k, v in value.items()
            }
            setattr(upd_obj, name, new_dict)

    return upd_obj

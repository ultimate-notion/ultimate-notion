"""Additional utilities that fit nowhere else."""

from __future__ import annotations

import datetime as dt
import textwrap
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
from hashlib import sha256
from itertools import chain
from pathlib import Path
from typing import Any, TypeVar

import numpy as np
import pendulum as pnd
from packaging.version import Version

from ultimate_notion import __version__

T = TypeVar('T')  # ToDo: Use new syntax when requires-python >= 3.12


class SList(list[T]):
    """A list that holds often only a single element."""

    def item(self) -> T:
        if len(self) == 1:
            return self[0]
        elif len(self) == 0:
            msg = 'list is empty'
        else:
            msg = f"list of '{type(self[0]).__name__}' objects has more than one element"
        raise ValueError(msg)


def flatten(nested_list: list[list[T]], /) -> list[T]:
    """Flatten a nested list."""
    return list(chain.from_iterable(nested_list))


def is_notebook() -> bool:
    """Determine if we are running within a Jupyter notebook."""
    try:
        from IPython import get_ipython  # noqa: PLC0415
    except ModuleNotFoundError:
        return False  # Probably standard Python interpreter
    else:
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True  # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)


def store_retvals(func):
    """Decorator storing the return values as function attribute for later cleanups.

    This can be used for instance in a generator like this:
    ```
    @pytest.fixture
    def create_blank_db(notion, test_area):
        @store_retvals
        def nested_func(db_name):
            db = notion.databases.create(
                parent=test_area,
                title=db_name,
                schema={
                    'Name': schema.Title(),
                },
            )
            return db

        yield nested_func

        # clean up by deleting the db of each prior call
        for db in nested_func.retvals:
            notion.databases.delete(db)
    ```
    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        retval = func(*args, **kwargs)
        wrapped.retvals.append(retval)
        return retval

    wrapped.retvals = []
    return wrapped


def find_indices(elements: np.ndarray | list[Any], total_set: np.ndarray | list[Any]) -> np.ndarray:
    """Finds the indices of the elements in the total set."""
    if not isinstance(total_set, np.ndarray):
        total_set = np.array(total_set)
    mask = np.isin(total_set, elements)
    indices = np.where(mask)[0]
    lookup = dict(zip(total_set[mask], indices, strict=True))
    result = np.array([lookup.get(x) for x in elements])
    return result


def find_index(elem: Any, lst: list[Any]) -> int | None:
    """Find the index of the element in the list or return `None`."""
    try:
        return lst.index(elem)
    except ValueError:
        return None


def deepcopy_with_sharing(obj: Any, shared_attributes: list[str], memo: dict[int, Any] | None = None):
    """Like `deepcopy` but specified attributes are shared.

    Deepcopy an object, except for a given list of attributes, which should
    be shared between the original object and its copy.

    Args:
        obj: some object to copy
        shared_attributes: A list of strings identifying the attributes that should be shared instead of copied.
        memo: dictionary passed into __deepcopy__.  Ignore this argument if not calling from within __deepcopy__.

    Example:
        ```python
        class A(object):
            def __init__(self):
                self.copy_me = []
                self.share_me = []

            def __deepcopy__(self, memo):
                return deepcopy_with_sharing(
                    self, shared_attribute_names=['share_me'], memo=memo
                )


        a = A()
        b = deepcopy(a)
        assert a.copy_me is not b.copy_me
        assert a.share_me is b.share_me

        c = deepcopy(b)
        assert c.copy_me is not b.copy_me
        assert c.share_me is b.share_me
        ```

    Original from https://stackoverflow.com/a/24621200
    """
    shared_attrs = {k: getattr(obj, k) for k in shared_attributes}

    deepcopy_defined = hasattr(obj, '__deepcopy__')
    if deepcopy_defined:
        # Do hack to prevent infinite recursion in call to deepcopy
        deepcopy_method = obj.__deepcopy__
        obj.__deepcopy__ = None

    for attr in shared_attributes:
        del obj.__dict__[attr]

    clone = deepcopy(obj, memo)

    for attr, val in shared_attrs.items():
        setattr(obj, attr, val)
        setattr(clone, attr, val)

    if deepcopy_defined:
        # Undo hack
        obj.__deepcopy__ = deepcopy_method
        del clone.__deepcopy__

    return clone


KT = TypeVar('KT')  # ToDo: Use new syntax when requires-python >= 3.12
VT = TypeVar('VT')  # ToDo: Use new syntax when requires-python >= 3.12


def dict_diff(dct1: dict[KT, VT], dct2: dict[KT, VT]) -> tuple[list[KT], list[KT], dict[KT, tuple[VT, VT]]]:
    """Returns the added keys, removed keys and keys of changed values of both dictionaries."""
    set1, set2 = set(dct1.keys()), set(dct2.keys())
    keys_added = list(set2 - set1)
    keys_removed = list(set1 - set2)
    values_changed = {key: (dct1[key], dct2[key]) for key in set1 & set2 if dct1[key] != dct2[key]}
    return keys_added, keys_removed, values_changed


def dict_diff_str(dct1: dict[KT, VT], dct2: dict[KT, VT]) -> tuple[str, str, str]:
    """Returns the added keys, removed keys and keys of changed values of both dictionaries as strings for printing."""
    keys_added, keys_removed, values_changed = dict_diff(dct1, dct2)
    keys_added_str = ', '.join([str(k) for k in keys_added]) or 'None'
    keys_removed_str = ', '.join([str(k) for k in keys_removed]) or 'None'
    keys_changed_str = ', '.join(f'{k}: {v[0]} -> {v[1]}' for k, v in values_changed.items()) or 'None'
    return keys_added_str, keys_removed_str, keys_changed_str


def convert_md_to_py(path: Path | str, *, target_path: Path | str | None = None) -> None:
    """Converts a Markdown file to a py file by extracting all python codeblocks

    Args:
        path: Path to the Markdown file to convert
        target_path: Path to save the new Python file. If not provided, the new file will be the same file with .py

    !!! warning

        If a file with the same name already exists, it will be overwritten.
    """
    if isinstance(path, str):
        path = Path(path)
    if not path.is_file():
        msg = f'{path} is no file!'
        raise RuntimeError(msg)

    if target_path is None:
        target_path = path.with_suffix('.py')
    elif isinstance(target_path, str):
        target_path = Path(target_path)

    md_str = path.read_text()

    def check_codeblock(block):
        first_line = block.split('\n')[0]
        if first_line[3:] != 'python':
            return ''
        return '\n'.join(block.split('\n')[1:])

    docstring = textwrap.dedent(md_str)
    in_block = False
    block = ''
    codeblocks = []
    for line in docstring.split('\n'):
        if line.startswith('```'):
            if in_block:
                codeblocks.append(check_codeblock(block))
                block = ''
            in_block = not in_block
        if in_block:
            block += line + '\n'
    py_str = '\n'.join([c for c in codeblocks if c != ''])

    target_path.with_suffix('.py').write_text(py_str)


def str_hash(*args: str, n_chars: int = 16) -> str:
    """Hashes string arguments to a n-character string."""
    return sha256(''.join(args).encode('utf-8')).hexdigest()[:n_chars]


def rank(arr: np.ndarray) -> np.ndarray:
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


def parse_dt_str(dt_str: str) -> pnd.DateTime | pnd.Date | pnd.Interval:
    """Parse a string to a pendulum object using the local timezone if none provided or UTC otherwise."""

    def set_tz(dt_spec: pnd.DateTime | pnd.Date | dt.datetime | dt.date) -> pnd.DateTime | pnd.Date:
        """Set the timezone of the datetime specifier object if necessary."""
        if isinstance(dt_spec, pnd.DateTime):
            if dt_spec.tz is None:
                return dt_spec.in_tz('local')
            else:
                return dt_spec.in_tz('UTC')  # to avoid unnamed timezones we convert to UTC
        elif isinstance(dt_spec, pnd.Date):
            return dt_spec  # as it is a date and has no tz information
        elif isinstance(dt_spec, dt.datetime):
            if dt_spec.tzinfo is None:
                return pnd.instance(dt_spec, tz='local')
            else:
                return pnd.instance(dt_spec).in_tz('UTC')  # to avoid unnamed timezones we convert to UTC
        elif isinstance(dt_spec, dt.date):
            return pnd.instance(dt_spec)
        else:
            msg = f'Unexpected type {type(dt_spec)} for {dt_spec}'
            raise TypeError(msg)

    dt_spec = pnd.parse(dt_str, exact=True, tz=None)
    if isinstance(dt_spec, pnd.DateTime):
        return set_tz(dt_spec)
    elif isinstance(dt_spec, pnd.Date):
        return dt_spec
    elif isinstance(dt_spec, pnd.Interval):
        return pnd.Interval(start=set_tz(dt_spec.start), end=set_tz(dt_spec.end))
    else:
        msg = f'Unexpected parsing result of type {type(dt_spec)} for {dt_str}'
        raise TypeError(msg)


def to_pendulum(dt_spec: str | dt.datetime | dt.date | pnd.Interval) -> pnd.DateTime | pnd.Date | pnd.Interval:
    """Convert a datetime or date object to a pendulum object."""
    if isinstance(dt_spec, pnd.DateTime | pnd.Date | pnd.Interval):
        return dt_spec
    elif isinstance(dt_spec, str):
        return parse_dt_str(dt_spec)
    elif isinstance(dt_spec, dt.datetime):
        if dt_spec.tzinfo is None:
            return pnd.instance(dt_spec, tz='local')
        else:
            return pnd.instance(dt_spec).in_tz('UTC')  # to avoid unnamed timezones we convert to UTC
    elif isinstance(dt_spec, dt.date):
        return pnd.instance(dt_spec)
    else:
        msg = f'Unexpected type {type(dt_spec)} for {dt_spec}'
        raise TypeError(msg)


@contextmanager
def temp_timezone(tz: str | pnd.Timezone):
    """Temporarily set the local timezone to the given timezone. Mostly used by unit tests."""
    if not isinstance(tz, pnd.Timezone):
        tz = pnd.timezone(tz)

    current_tz = pnd.local_timezone()
    if not isinstance(current_tz, pnd.Timezone):
        msg = f'Expected a Timezone object but got type {type(current_tz)}.'
        raise RuntimeError(msg)
    pnd.set_local_timezone(tz)
    try:
        yield
    finally:
        pnd.set_local_timezone(current_tz)

"""Additional utilities that fit nowhere else."""

from __future__ import annotations

import datetime
import textwrap
from copy import deepcopy
from datetime import tzinfo
from functools import wraps
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeAlias, TypeVar, cast
from uuid import UUID

import numpy as np

from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.core import GenericObject

if TYPE_CHECKING:
    from ultimate_notion.session import Session


ObjRef: TypeAlias = UUID | str


T = TypeVar('T')


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
                    "Name": schema.Title(),
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
    if elem not in lst:
        return None
    else:
        return lst.index(elem)


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
                    self, shared_attribute_names=["share_me"], memo=memo
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


def get_url(object_id: UUID | str) -> str:
    """Return the URL for the object with the given id."""
    object_id = object_id if isinstance(object_id, UUID) else UUID(object_id)
    return f'https://notion.so/{object_id.hex}'


def get_uuid(obj: str | UUID | objs.ParentRef | objs.NotionObject | objs.BlockRef) -> UUID:
    """Retrieves a UUID from an object reference.

    Only meant for internal use.
    """
    return objs.ObjectReference.build(obj).id


KT = TypeVar('KT')
VT = TypeVar('VT')


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


Self = TypeVar('Self', bound='Wrapper[Any]')  # ToDo: Replace when requires-python >= 3.11
GT = TypeVar('GT', bound=GenericObject)  # ToDo: Use new syntax when requires-python >= 3.12


class ObjRefWrapper(Protocol[GT]):
    """Wrapper for objects that have an obj_ref attribute.

    Note: This allows us to define Mixin classes that require the obj_ref attribute.
    """

    obj_ref: GT


class Wrapper(ObjRefWrapper[GT]):
    """Convert objects from the obj-based API to the high-level API and vice versa."""

    obj_ref: GT

    _obj_api_map: ClassVar[dict[type[GT], type[Wrapper]]] = {}  # type: ignore[misc]

    def __init_subclass__(cls, wraps: type[GT], **kwargs: Any):
        super().__init_subclass__(**kwargs)
        cls._obj_api_map[wraps] = cls

    def __new__(cls: type[Wrapper], *args, **kwargs) -> Wrapper:
        # Needed for wrap_obj_ref and its call to __new__ to work!
        return super().__new__(cls)

    def __init__(self, *args: Any, **kwargs: Any):
        """Default constructor that also builds `obj_ref`."""
        obj_api_type: type[GenericObject] = self._obj_api_map_inv[self.__class__]
        self.obj_ref = obj_api_type.build(*args, **kwargs)

    @classmethod
    def wrap_obj_ref(cls: type[Self], obj_ref: GT, /) -> Self:
        """Wraps `obj_ref` into a high-level object for the API of Ultimate Notion."""
        hl_cls = cls._obj_api_map[type(obj_ref)]
        hl_obj = hl_cls.__new__(hl_cls)
        hl_obj.obj_ref = obj_ref
        return cast(Self, hl_obj)

    @property
    def _obj_api_map_inv(self) -> dict[type[Wrapper], type[GT]]:
        return {v: k for k, v in self._obj_api_map.items()}


def get_active_session() -> Session:
    """Return the current active session or raise an exception.

    Avoids cyclic imports when used within the package itself.
    For internal use mostly.
    """
    from ultimate_notion.session import Session  # noqa: PLC0415

    return Session.get_active()


def get_repr(obj: Any, /, *, name: Any = None, desc: Any = None) -> str:
    """Default representation, i.e. `repr(...)`, used by us for consistency."""
    type_str = str(name) if name is not None else obj.__class__.__name__
    desc_str = str(desc) if desc is not None else str(obj)
    return f"<{type_str}: '{desc_str}' at {hex(id(obj))}>"


def convert_md_to_py(path: Path | str):
    """Converts a Markdown file to a py file by extracting all python codeblocks"""
    if isinstance(path, str):
        path = Path(path)
    if not path.is_file():
        msg = f'{path} is no file!'
        raise RuntimeError(msg)

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

    path.with_suffix('.py').write_text(py_str)


def str_hash(*args: str, n_chars: int = 16) -> str:
    """Hashes string arguments to a n-character string."""
    return sha256(''.join(args).encode('utf-8')).hexdigest()[:n_chars]


def local_time_zone() -> tzinfo:
    """Returns the local time zone."""
    tzinfo = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    if tzinfo is None:
        msg = 'Could not determine local time zone!'
        raise RuntimeError(msg)
    return tzinfo


def rank(arr: np.ndarray) -> np.ndarray:
    """Returns the rank of the elements in the array and gives the same rank to equal elements."""
    mask = np.argsort(arr)
    rank = np.zeros_like(arr)
    rank[1:] = np.cumsum(np.where(np.diff(arr[mask]) != 0, 1, 0))
    return rank[np.argsort(mask)]

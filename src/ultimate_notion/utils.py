"""Additional utilities that fit nowhere else"""
from collections.abc import Callable
from copy import deepcopy
from functools import wraps
from typing import Any, TypeAlias, TypeVar
from uuid import UUID

import numpy as np
from notion_client.errors import APIResponseError
from polling2 import poll

from ultimate_notion.obj_api import types
from ultimate_notion.record import Record

T = TypeVar('T')
ObjRef: TypeAlias = UUID | str


class SList(list[T]):
    """A list that holds often only a single element"""

    def item(self) -> T:
        if len(self) == 1:
            return self[0]
        elif len(self) == 0:
            msg = 'list is empty'
        else:
            msg = f"list of '{type(self[0]).__name__}' objects has more than one element"
        raise ValueError(msg)


def is_notebook() -> bool:
    try:
        from IPython import get_ipython

        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True  # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False  # Probably standard Python interpreter


def store_retvals(func):
    """Decorator storing the return values as function attribute for later cleanups

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


def find_indices(elements: np.ndarray | list[Any], total_set: np.ndarray | list[Any]) -> np.array:
    """Finds the indices of the elements in the total set"""
    if not isinstance(total_set, np.ndarray):
        total_set = np.array(total_set)
    mask = np.isin(total_set, elements)
    indices = np.where(mask)[0]
    lookup = dict(zip(total_set[mask], indices, strict=True))
    result = np.array([lookup.get(x, None) for x in elements])
    return result


def find_index(elem: Any, lst: list[Any]) -> int | None:
    """Find the index of the element in the list or return `None`"""
    if elem not in lst:
        return None
    else:
        return lst.index(elem)


def deepcopy_with_sharing(obj: Any, shared_attributes: list[str], memo: dict[int, Any] | None = None):
    """
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


def get_uuid(obj: ObjRef | types.ParentRef | types.GenericObject) -> UUID:
    """Retrieves a UUID from an object reference using Notional

    Only meant for internal use.
    """
    return types.ObjectReference[obj].id


def wait_until_exists(record: Record, step: int = 1, timeout: int = 10):
    """Wait until object exists after creation

    In most cases, this is not really necessary to use.
    """
    from ultimate_notion.database import Database
    from ultimate_notion.page import Page

    poll_func: Callable[[UUID | str], Record]
    if isinstance(record, Database):
        poll_func = record.session.get_db
    elif isinstance(record, Page):
        poll_func = record.session.get_page
    else:  # Todo: Should we handle blocks here too?
        msg = f'Unknown object type: {type(record)}'
        raise RuntimeError(msg)

    poll(lambda: poll_func(record.id), step=step, timeout=timeout, ignore_exceptions=(APIResponseError,))


def decapitalize(string: str) -> str:
    """Inverse of capitalize"""
    return string[0].lower() + string[1:]

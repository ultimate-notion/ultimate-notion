"""Additional utilities that fit nowhere else"""
from typing import List, TypeVar

T = TypeVar('T')


class SList(list, List[T]):
    """A list that holds often only a single element"""

    def item(self) -> T:
        if len(self) == 1:
            return self[0]
        elif len(self) == 0:
            msg = "list is empty"
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

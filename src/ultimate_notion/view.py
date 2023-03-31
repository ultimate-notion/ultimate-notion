"""View representing the result of a Query"""
from __future__ import annotations

from html import escape as htmlescape
from typing import TYPE_CHECKING, Any, List, Optional, Union

import numpy as np
import pandas as pd
from emoji import is_emoji
from notional.schema import Title
from tabulate import tabulate

from .page import Page
from .utils import SList, deepcopy_with_sharing, find_index, find_indices, is_notebook

if TYPE_CHECKING:
    from .database import Database

ColType = Union[str, List[str]]


class View:
    def __init__(self, database: Database, pages: List[Page]):
        self.database = database
        self._title_col = SList(col for col, val in database.schema.items() if isinstance(val, Title)).item()
        self._columns = self._get_columns(self._title_col)
        self._pages = np.array(pages)

        self.reset()

    def _get_columns(self, title_col: str) -> np.ndarray:
        """Make sure title column is the first columns"""
        cols = list(self.database.schema.keys())
        cols.insert(0, cols.pop(cols.index(title_col)))
        return np.array(cols)

    def reset(self) -> View:
        """Reset the view, i.e. remove filtering, index and sorting"""
        self._icon_name: Optional[str] = None
        self._id_name: Optional[str] = None
        self._index_name: Optional[str] = None
        self._row_indices = np.arange(len(self._pages))
        self._col_indices = np.arange(len(self._columns))
        return self

    def clone(self) -> View:
        """Clone the current view"""
        return deepcopy_with_sharing(self, shared_attributes=["database", "_pages"])

    def __len__(self):
        return len(self._row_indices)

    @property
    def columns(self) -> List[str]:
        """Columns of the database view aligned with the elements of a row"""
        cols = list(self._columns[self._col_indices])
        if self.has_icon:
            assert self._icon_name is not None
            cols.insert(0, self._icon_name)
        if self.has_id:
            assert self._id_name is not None
            cols.insert(0, self._id_name)
        if self.has_index:
            assert self._index_name is not None
            cols.insert(0, self._index_name)
        return cols

    def page(self, idx: int) -> Page:
        """Retrieve a page by index of the view

        Returned pages are clones of the ones from the view and thus modifications
        will not be reflected in the view. Use `apply` to modify the actual pages
        of the database.
        """
        return self._pages[self._row_indices[idx]].clone()

    def pages(self) -> List[Page]:
        """Retrieve all pages in view"""
        return [self.page(idx) for idx in range(len(self))]

    def row(self, idx: int) -> List[Any]:
        page = self.page(idx)
        page_dct = page.to_dict()
        row = []
        for col in self.columns:
            if col == self._title_col:
                row.append(page.title)
            elif col == self._id_name:
                row.append(page.id)
            elif col == self._index_name:
                row.append(idx)
            elif col == self._icon_name:
                row.append(page.icon)
            else:
                row.append(page_dct[col])
        return row

    def rows(self) -> List[List[Any]]:
        return [self.row(idx) for idx in range(len(self))]

    def _html_for_icon(self, rows: List[Any], cols: List[str]) -> List[Any]:
        # escape everything as we ask tabulate not to do it
        rows = [[htmlescape(elem) if isinstance(elem, str) else elem for elem in row] for row in rows]
        if (title_idx := find_index(self._icon_name, cols)) is None:
            return rows
        for idx, row in enumerate(rows):
            page = self.page(idx)
            if is_emoji(page.icon):
                row[title_idx] = f"{page.icon}"
            else:  # assume it's an external image resource that html can load directly
                row[title_idx] = f'<img src="{page.icon}" style="height:1em">'
        return rows

    def show(self, html: Optional[bool] = None):
        """Show the view

        Args:
            html: output in html or not, or determine automatically based on context, e.g. Jupyter lab.
        """
        rows = self.rows()
        cols = self.columns

        if html is None:
            html = is_notebook()

        if html:
            if self.has_icon:
                rows = self._html_for_icon(rows, cols)
                html_str = tabulate(rows, headers=cols, tablefmt="unsafehtml")
            else:
                html_str = tabulate(rows, headers=cols, tablefmt="html")
            return html_str
        else:
            return tabulate(rows, headers=cols)

    def __repr__(self) -> str:
        repr_str = self.show()
        if is_notebook():
            from IPython.core.display import display_html

            display_html(repr_str)
        else:
            return repr_str

    def __str__(self) -> str:
        return self.show(html=False)

    @property
    def has_index(self) -> bool:
        return self._index_name is not None

    def with_index(self, name="index") -> View:
        """Add an index column to the view"""
        if self.has_index and name == self._index_name:
            return self

        assert name not in self.columns, f"index '{name}' is already a column name"
        view = self.clone()
        view._index_name = name
        return view

    def without_index(self) -> View:
        """Remove index column from the view"""
        if not self.has_index:
            return self

        view = self.clone()
        view._index_name = None
        return view

    @property
    def has_icon(self) -> bool:
        return self._icon_name is not None

    def with_icon(self, name="icon") -> View:
        """Show icons in HTML output"""
        if self.has_icon and name == self._icon_name:
            return self

        view = self.clone()
        view._icon_name = name
        return view

    def without_icon(self) -> View:
        """Don't show icons in HTML output"""
        if not self.has_icon:
            return self

        view = self.clone()
        view._icon_name = None
        return view

    @property
    def has_id(self) -> bool:
        return self._id_name is not None

    def with_id(self, name: str = "id") -> View:
        """Add an id column to the view"""
        if self.has_id and name == self._id_name:
            return self

        view = self.clone()
        view._id_name = name
        return view

    def without_id(self) -> View:
        """Remove id column from the view"""
        if not self.has_id:
            return self

        view = self.clone()
        view._id_name = None
        return view

    def head(self, num: int) -> View:
        """Keep only the first `num` elements in view"""
        view = self.clone()
        view._row_indices = view._row_indices[:num]
        return view

    def limit(self, num: int) -> View:
        """Alias for `head`"""
        return self.head(num)

    def tail(self, num: int) -> View:
        """Keep only the last `num` elements in view"""
        view = self.clone()
        view._row_indices = view._row_indices[-num:]
        return view

    def to_pandas(self) -> pd.DataFrame:
        # remove index as pandas uses its own
        view = self.without_index() if self.has_index else self
        return pd.DataFrame(view.rows(), columns=view.columns)

    def select(self, cols: ColType, *more_cols: str) -> View:
        if isinstance(cols, str):
            cols = [cols]
        if more_cols:
            cols += more_cols

        curr_cols = self._columns  # we only consider non-meta columns, e.g. no index, etc.
        if not_included := set(cols) - set(curr_cols):
            raise RuntimeError(f"Some columns, i.e. {', '.join(not_included)}, are not in view")

        view = self.clone()
        select_col_indices = find_indices(cols, curr_cols)
        view._col_indices = view._col_indices[select_col_indices]
        return view

    def apply(self, udf):
        """Apply function to all pages in view"""
        raise NotImplementedError

    def reverse(self) -> View:
        """Reverse the order of the rows"""
        view = self.clone()
        view._row_indices = view._row_indices[::-1]
        return view

    def sort(self):
        raise NotImplementedError

    def filter(self):
        raise NotImplementedError

    def reload(self):
        """Reload all pages by re-executing the query that generated the view"""
        raise NotImplementedError

    def upload(self):
        """Push all modified pages to Notion"""
        raise NotImplementedError

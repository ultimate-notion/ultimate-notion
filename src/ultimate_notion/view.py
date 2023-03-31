"""View representing the result of a Query

ToDo:
    * also show icon
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Union

import numpy as np
import pandas as pd
from emoji import is_emoji
from notional.schema import Title
from tabulate import tabulate

from .page import Page
from .utils import SList, find_indices, is_notebook

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
        self._with_icons = True
        self._has_index = False
        self._index_name: Optional[str] = None
        self._row_indices = np.arange(len(self._pages))
        self._col_indices = np.arange(len(self._columns))
        return self

    def clone(self) -> View:
        """Clone the current view"""
        view = View(self.database, list(self._pages))

        view._with_icons = self._with_icons
        view._has_index = self._has_index
        view._index_name = self._index_name
        view._row_indices = self._row_indices
        view._col_indices = self._col_indices
        return view

    def __len__(self):
        return len(self._row_indices)

    @property
    def has_index(self):
        return self._has_index

    @property
    def columns(self) -> List[str]:
        """Columns of the database view"""
        return list(self._columns[self._col_indices])

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
        page_dct = self.page(idx).to_dict()
        row = [idx] if self.has_index else []
        for col in self.columns:
            if col == self._title_col:
                row.append(page_dct['title'])
            else:
                row.append(page_dct[col])
        return row

    def rows(self) -> List[List[Any]]:
        return [self.row(idx) for idx in range(len(self))]

    def _html_for_icon(self, rows: List[Any], cols: List[str]) -> List[Any]:
        if self._title_col not in cols:
            return rows
        title_idx = cols.index(self._title_col)
        for idx, row in enumerate(rows):
            page = self.page(idx)
            if is_emoji(page.icon):
                row[title_idx] = f"{page.icon} {row[title_idx]}"
            else:
                row[title_idx] = f'<img src="{page.icon}" style="height:1em;float:left">{row[title_idx]}'
        return rows

    def show(self, html: Optional[bool] = None):
        """Show the view

        Args:
            html: display in html or not, or determine automatically based on context, e.g. Jupyter lab.
        """
        rows = self.rows()
        cols = self.columns

        if self.has_index:
            assert self._index_name is not None
            cols.insert(0, self._index_name)

        if html or (html is None and is_notebook()):
            from IPython.core.display import display_html

            if self._with_icons:
                rows = self._html_for_icon(rows, cols)
                return display_html(tabulate(rows, headers=cols, tablefmt="unsafehtml"))
            else:
                return display_html(tabulate(rows, headers=cols, tablefmt="html"))
        else:
            return tabulate(rows, headers=cols)

    def __repr__(self) -> str:
        return self.show()

    def __str__(self) -> str:
        return self.show(html=False)

    def with_index(self, name="index") -> View:
        """Display the index as first column when printing"""
        if self.has_index:
            return self

        assert name not in self.columns, f"index '{name}' is already a column name"
        view = self.clone()
        view._has_index = True
        view._index_name = name
        return view

    def without_index(self) -> View:
        """Do not show the index as first column when printing"""
        if not self.has_index:
            return self

        view = self.clone()
        view._has_index = False
        view._index_name = None
        return view

    def with_icons(self) -> View:
        """Show icons in HTML output"""
        self._with_icons = True
        return self

    def without_icons(self) -> View:
        """Don't show icons in HTML output"""
        self._with_icons = False
        return self

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
        view = self.without_index() if self.has_index else self
        return pd.DataFrame(view.rows(), columns=view.columns)

    def select(self, cols: ColType, *more_cols: str) -> View:
        if isinstance(cols, str):
            cols = [cols]
        if more_cols:
            cols += more_cols

        if not_included := set(cols) - set(self.columns):
            raise RuntimeError(f"Some columns, i.e. {', '.join(not_included)}, are not in view")

        view = self.clone()
        select_col_indices = find_indices(cols, self.columns)
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

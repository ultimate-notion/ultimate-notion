"""View representing the result of a Query"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

import pandas as pd
from notional.schema import Title
from tabulate import tabulate

from .page import Page
from .utils import SList, is_notebook

if TYPE_CHECKING:
    from .database import Database


class View:
    def __init__(self, database: Database, pages: List[Page]):
        self.database = database
        self.pages = pages
        self.columns = list(self.database.properties.keys())
        self._title_col = SList(col for col, val in database.properties.items() if isinstance(val, Title)).item()
        self._has_index = False
        self._index_name = None

    def __str__(self) -> Optional[str]:
        rows = self.rows()

        if is_notebook():
            from IPython.core.display import display_html

            return display_html(tabulate(rows, headers=self.columns, tablefmt="html"))
        else:
            return tabulate(rows, headers=self.columns)

    @property
    def has_index(self):
        return self._has_index

    def row(self, idx: int) -> List[Any]:
        page_dct = self.pages[idx].to_dict()
        row = []
        for col in self.columns:
            if col == self._title_col:
                row.append(page_dct['title'])
            elif col == self._index_name:
                row.append(idx)
            else:
                row.append(page_dct[col])
        return row

    def rows(self) -> List[List[Any]]:
        return [self.row(idx) for idx in range(len(self.pages))]

    def clone(self) -> View:
        view = View(self.database, self.pages[:])
        view.columns = self.columns[:]
        view._has_index = self._has_index
        view._index_name = self._index_name
        return view

    def with_index(self, name="index") -> View:
        assert name not in self.columns, f"index '{name}' is already a column name"
        assert not self._has_index, f"an index '{self._index_name}' already exists"
        view = self.clone()
        view._has_index = True
        view._index_name = name
        view.columns.insert(0, name)
        return view

    def without_index(self) -> View:
        assert self.has_index, "there is no index"
        view = self.clone()
        view.columns.remove(self._index_name)
        view._has_index = False
        view._index_name = None
        return view

    def limit(self, num: int) -> View:
        view = self.clone()
        view.pages = view.pages[:num]
        return view

    def as_df(self) -> pd.DataFrame:
        if self.has_index:
            view = self.without_index()
        else:
            view = self
        return pd.DataFrame(view.rows(), columns=view.columns)

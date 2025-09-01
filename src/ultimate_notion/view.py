"""View representing the result of a Query."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from html import escape as htmlescape
from typing import TYPE_CHECKING, Any, TypeVar, cast, overload

import numpy as np
from pydantic import BaseModel
from tabulate import tabulate

from ultimate_notion import props, schema
from ultimate_notion.core import Wrapper, get_repr
from ultimate_notion.file import ExternalFile, NotionFile
from ultimate_notion.obj_api.enums import FormulaType, RollupType
from ultimate_notion.page import Page
from ultimate_notion.props import Option
from ultimate_notion.rich_text import html_img
from ultimate_notion.schema import Property
from ultimate_notion.user import User
from ultimate_notion.utils import SList, deepcopy_with_sharing, find_index, find_indices, is_notebook, rec_apply

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
    from numpy.typing import NDArray

    from ultimate_notion.database import Database
    from ultimate_notion.props import PropertyValue
    from ultimate_notion.query import Query

T = TypeVar('T')


class View(Sequence[Page]):
    def __init__(self, database: Database, pages: Sequence[Page], query: Query):
        self.database = database
        self._query = query
        self._title_col = database.schema.get_title_prop().name
        self._columns = self._get_columns(self._title_col)
        self._pages: NDArray[Any] = np.array(pages)
        self._row_indices: NDArray[Any]
        self._col_indices: NDArray[Any]
        self.default_limit = 10

        self.reset()

    def reset(self) -> View:
        """Reset the view, i.e. remove filtering, index and sorting."""
        self._icon_name: str | None = None
        self._id_name: str | None = None
        self._index_name: str | None = None
        self._row_indices = np.arange(len(self._pages))
        self._col_indices = np.arange(len(self._columns))
        return self

    def clone(self) -> View:
        """Clone the current view."""
        return deepcopy_with_sharing(self, shared_attributes=['database', '_pages', '_query'])

    def _get_columns(self, title_col: str) -> NDArray[Any]:
        """Make sure title column is the first columns."""
        cols = list(self.database.schema.to_dict().keys())
        cols.insert(0, cols.pop(cols.index(title_col)))
        return np.array(cols)

    @property
    def columns(self) -> list[str]:
        """Columns/properties of the database view aligned with the elements of a row."""
        cols = list(self._columns[self._col_indices])
        if self.has_icon:
            cols.insert(0, self._icon_name)
        if self.has_id:
            cols.insert(0, self._id_name)
        if self.has_index:
            cols.insert(0, self._index_name)
        return cols

    @overload
    def __getitem__(self, idx: int, /) -> Page: ...

    @overload
    def __getitem__(self, idx: slice, /) -> Sequence[Page]: ...

    def __getitem__(self, idx: int | slice, /) -> Page | Sequence[Page]:
        pages = self._pages[self._row_indices[idx]]
        if isinstance(idx, slice):
            return tuple(pages)
        else:
            return cast(Page, pages)

    def get_page(self, idx: int, /) -> Page:
        """Retrieve a page by index of the view."""
        return cast(Page, self._pages[self._row_indices[idx]])

    def search_page(self, name: str) -> SList[Page]:
        """Retrieve a page from this view by name"""
        pages = [page for page in self.to_pages() if page.title == name]
        return SList(pages)

    def get_row(self, idx: int, /) -> tuple[Any, ...]:
        """Retrieve a row, i.e. all properties of a page defined by an index."""
        page = self.get_page(idx)
        row: list[Any] = []
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
                row.append(page.props[col])
        return tuple(row)

    def to_pages(self) -> list[Page]:
        """Convert the view to a simple list of pages."""
        return [self.get_page(idx) for idx in range(len(self))]

    def to_rows(self) -> list[tuple[Any, ...]]:
        return [self.get_row(idx) for idx in range(len(self))]

    def to_pydantic(self) -> list[BaseModel]:
        """Convert the view to a list of Pydantic models."""
        model = self.database.schema.to_pydantic_model(with_ro_props=True)
        is_prop_ro = {prop.name: prop.readonly for prop in self.database.schema.get_props()}

        def get_prop(page: Page, prop: str) -> PropertyValue | Any:
            prop_value = page.props._get_property(prop)
            return prop_value if is_prop_ro[prop] else prop_value.value

        models: list[BaseModel] = []
        for page in self.to_pages():
            models.append(model(**{col: get_prop(page, col) for col in self.columns}))

        return models

    def to_pandas(self) -> pd.DataFrame:
        """Convert the view to a Pandas dataframe."""
        import pandas as pd  # noqa: PLC0415

        # remove index as pandas uses its own
        view = self.without_index() if self.has_index else self
        data = rec_apply(cmplx_to_str, self.to_rows())

        return pd.DataFrame(data, columns=view.columns)

    def _probe_col_type(self, col: str) -> PropertyValue | None:
        """Probe the type of a column by checking the values in the column."""
        for page in self.to_pages():
            match prop := page.props._get_property(col):
                case props.Relations():
                    # we can only determine the type of a relation if it has at least one value
                    if prop.value:
                        return prop
                case _:
                    return prop
        return None

    def _to_polars_schema(self) -> dict[str, pl.DataType]:
        """Create a Polars schema for the view."""
        import polars as pl  # noqa: PLC0415

        db_schema = self.database.schema.to_dict()
        pl_schema: dict[str, pl.DataType] = {}
        for col in self.columns:
            if col in db_schema:
                prop_type: Property | PropertyValue = db_schema[col]
                if isinstance(prop_type, schema.Rollup | schema.Relation | schema.Formula):
                    prop_type = probed_type if (probed_type := self._probe_col_type(col)) is not None else prop_type
                pl_schema[col] = prop_type_to_polars(prop_type)
            elif col == self._icon_name:
                pl_schema[col] = pl.String()
            elif col == self._index_name:
                pl_schema[col] = pl.Int64()
            elif col == self._id_name:
                pl_schema[col] = pl.String()
            else:
                msg = f'Column `{col}` not found in database schema.'
                raise RuntimeError(msg)
        return pl_schema

    def to_polars(self) -> pl.DataFrame:
        """Convert the view to a Polars dataframe."""
        import polars as pl  # noqa: PLC0415

        data = rec_apply(cmplx_to_str, self.to_rows())
        schema = self._to_polars_schema()
        return pl.DataFrame(data=data, schema=schema, orient='row')

    def _html_for_icon(self, rows: list[Any], cols: list[str]) -> list[Any]:
        # escape everything as we ask tabulate not to do it
        rows = [[htmlescape(elem) if isinstance(elem, str) else elem for elem in row] for row in rows]
        if (title_idx := find_index(self._icon_name, cols)) is None:
            return rows
        for idx, row in enumerate(rows):
            page = self.get_page(idx)
            icon = html_img(page.icon.url, size=1.2) if isinstance(page.icon, NotionFile | ExternalFile) else page.icon
            row[title_idx] = icon
        return rows

    def as_table(self, tablefmt: str | None = None) -> str:
        """Return the view in a given string table format.

        Some table formats:

        - plain: no pseudographics
        - simple: Pandoc's simple table, i.e. only dashes to separate header from content
        - github: GitHub flavored Markdown
        - simple_grid: uses dashes & pipes to separate cells
        - html: standard html markup

        Find more table formats under: https://github.com/astanin/python-tabulate#table-format
        """
        rows = self.to_rows()
        cols = self.columns

        if tablefmt is None:
            tablefmt = 'html' if is_notebook() else 'simple'

        if tablefmt == 'html':
            if self.has_icon:
                rows = self._html_for_icon(rows, cols)
                html_str = str(tabulate(rows, headers=cols, tablefmt='unsafehtml'))  # str() as tabulate wraps the str
            else:
                html_str = str(tabulate(rows, headers=cols, tablefmt='html'))  # str() as tabulate wraps the str
            return html_str
        else:
            return tabulate(rows, headers=cols, tablefmt=tablefmt)

    def show(self, *, simple: bool | None = None) -> None:
        """Show the database as human-readable table."""
        if simple:
            tablefmt = 'simple'
        elif simple is None:
            tablefmt = 'html' if is_notebook() else 'simple'
        else:
            tablefmt = 'html'

        table_str = self.as_table(tablefmt=tablefmt)

        if is_notebook() and (tablefmt == 'html'):
            from IPython.display import display_html  # noqa: PLC0415

            display_html(table_str)
        else:
            print(table_str)  # noqa: T201

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically to display this view."""
        if len(self) > self.default_limit:
            html_str = self.limit(self.default_limit).as_table(tablefmt='html')
            html_str = f'<div style="display: inline-block;text-align: center;">{html_str}&#8942;</div></div>\n'
            return html_str
        else:
            return self.as_table(tablefmt='html')

    def __iter__(self) -> Iterator[Page]:
        """Iterate over the pages in the view."""
        return iter(self.to_pages())

    def __repr__(self) -> str:
        return get_repr(self, desc=self.database.title)

    def __str__(self) -> str:
        return self.as_table()

    def __len__(self) -> int:
        return len(self._row_indices)

    @property
    def is_empty(self) -> bool:
        """Is this view empty?"""
        return len(self) == 0

    def __bool__(self) -> bool:
        """Overwrite default behaviour."""
        msg = 'Use .is_empty instead of bool(view) to check if a view is empty.'
        raise RuntimeError(msg)

    @property
    def has_index(self) -> bool:
        return self._index_name is not None

    def with_index(self, name: str = 'index') -> View:
        """Add an index column to the view."""
        if self.has_index and name == self._index_name:
            return self

        if name in self.columns:
            msg = f"index '{name}' is already a column name"
            raise RuntimeError(msg)

        view = self.clone()
        view._index_name = name
        return view

    def without_index(self) -> View:
        """Remove index column from the view."""
        if not self.has_index:
            return self

        view = self.clone()
        view._index_name = None
        return view

    @property
    def has_icon(self) -> bool:
        return self._icon_name is not None

    def with_icon(self, name: str = 'icon') -> View:
        """Show icons in HTML output."""
        if self.has_icon and name == self._icon_name:
            return self

        view = self.clone()
        view._icon_name = name
        return view

    def without_icon(self) -> View:
        """Don't show icons in HTML output."""
        if not self.has_icon:
            return self

        view = self.clone()
        view._icon_name = None
        return view

    @property
    def has_id(self) -> bool:
        return self._id_name is not None

    def with_id(self, name: str = 'id') -> View:
        """Add an id column to the view."""
        if self.has_id and name == self._id_name:
            return self

        view = self.clone()
        view._id_name = name
        return view

    def without_id(self) -> View:
        """Remove id column from the view."""
        if not self.has_id:
            return self

        view = self.clone()
        view._id_name = None
        return view

    def head(self, num: int) -> View:
        """Keep only the first `num` elements in view."""
        view = self.clone()
        view._row_indices = view._row_indices[:num]
        return view

    def limit(self, num: int) -> View:
        """Alias for `head`"""
        return self.head(num)

    def tail(self, num: int) -> View:
        """Keep only the last `num` elements in view."""
        view = self.clone()
        view._row_indices = view._row_indices[-num:]
        return view

    def select(self, *cols: str) -> View:
        """Select columns for the view"""
        curr_cols = self._columns  # we only consider non-meta columns, e.g. no index, etc.
        if not_included := set(cols) - set(curr_cols):
            msg = f'Some columns, i.e. {", ".join(not_included)}, are not in view'
            raise RuntimeError(msg)

        view = self.clone()
        select_col_indices = find_indices(list(cols), curr_cols)
        view._col_indices = view._col_indices[select_col_indices]
        return view

    def apply(self, func: Callable[[Page], T]) -> list[T]:
        """Apply function to all pages in view.

        Args:
            func: function taking a Page as input
        """
        return [func(page) for page in self.to_pages()]

    def reverse(self) -> View:
        """Reverse the order of the rows."""
        view = self.clone()
        view._row_indices = view._row_indices[::-1]
        return view

    def sort(self) -> View:
        """Sort the view with respect to some columns."""
        # ToDo: Implement me
        raise NotImplementedError

    def filter(self) -> View:
        """Filter the view."""
        # ToDo: Implement me
        raise NotImplementedError

    def reload(self) -> View:
        """Reload all pages by re-executing the query that generated the view."""
        view = self.clone()
        view._pages = np.array(self._query.execute().to_pages())
        return view


def cmplx_to_str(obj: Wrapper) -> Wrapper | str:
    """Convert complex objects to a string representation."""
    match obj:
        case NotionFile() | ExternalFile():
            return obj.url
        case Option():
            return obj.name
        case User():
            return str(obj)
        case _:
            return obj


def prop_type_to_polars(prop_valtype: Property | PropertyValue) -> pl.DataType:
    """Convert a Notion property type to a Polars data type."""
    import polars as pl  # noqa: PLC0415

    match prop_valtype:
        case schema.Title() | schema.Text() | props.Title() | props.Text():
            return pl.String()
        case schema.ID() | props.ID():
            return pl.String()
        case schema.Verification() | props.Verification():
            return pl.Object()
        case schema.Button() | props.Button():
            return pl.Object()
        case schema.Number() | props.Number():
            return pl.Float64()
        case schema.Select() as prop:
            return pl.Enum([opt.name for opt in prop.options])
        case props.Select():
            return pl.Categorical()
        case schema.MultiSelect() as prop:
            return pl.List(pl.Enum([opt.name for opt in prop.options]))
        case schema.MultiSelect():
            return pl.List(pl.Categorical)
        case schema.Checkbox() | props.Checkbox():
            return pl.Boolean()
        case schema.Date() | props.Date():
            return pl.Datetime(time_unit='ms')
        case schema.Files() | schema.Person() | props.Files() | props.Person():
            # Fix 2025-06-06: `not yet implemented: Nested object types` pl.List(pl.Object()) not working
            return pl.List(pl.String())
        case schema.CreatedTime() | schema.LastEditedTime() | props.CreatedTime() | props.LastEditedTime():
            return pl.Datetime(time_unit='ms')
        case schema.CreatedBy() | schema.LastEditedBy() | props.CreatedBy() | props.LastEditedBy():
            return pl.Object()
        case schema.URL() | schema.Email() | schema.Phone() | props.URL() | props.Email() | props.Phone():
            return pl.String()
        case schema.Status() as prop:
            return pl.Enum([opt.name for opt in prop.options])
        case props.Status():
            return pl.Categorical()
        case props.Formula() as prop:
            match prop.value_type:
                case FormulaType.NUMBER:
                    return pl.Float64()
                case FormulaType.STRING:
                    return pl.String()
                case FormulaType.BOOLEAN:
                    return pl.Boolean()
                case FormulaType.DATE:
                    return pl.Datetime(time_unit='ms')
                case _:
                    msg = f'Unsupported formula type: {prop.value_type}'
                    raise ValueError(msg)
        case props.Rollup() as prop:
            match prop.value_type:
                case RollupType.NUMBER:
                    return pl.Float64()
                case RollupType.DATE:
                    return pl.Datetime(time_unit='ms')
                case RollupType.ARRAY:
                    # Fix 2025-06-06: `not yet implemented: Nested object types` pl.List(pl.Object()) not working
                    return pl.List(pl.String())
                case _:
                    msg = f'Unsupported rollup type: {prop.value_type}'
                    raise ValueError(msg)

        case schema.Relation() | schema.Rollup() | schema.Formula():
            # fallback as we cannot convert due to a lack of actual type information in the schema types
            return pl.Object()
        case _:
            msg = f'Unsupported property type or value: {prop_valtype}'
            raise ValueError(msg)

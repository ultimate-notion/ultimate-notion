"""Query the database for pages."""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, Field
from typing_extensions import Self

from ultimate_notion import schema
from ultimate_notion.core import get_active_session
from ultimate_notion.obj_api import query as obj_query
from ultimate_notion.obj_api.enums import SortDirection
from ultimate_notion.page import Page
from ultimate_notion.view import View

if TYPE_CHECKING:
    from ultimate_notion.database import Database


class Property(BaseModel):
    """Represents a property of a page."""

    prop_name: str
    sort_direction: SortDirection = Field(default=SortDirection.ASCENDING)

    def __hash__(self) -> int:
        return hash(self.prop_name)

    def __eq__(self, other: Any) -> Equals:
        return Equals(prop=self, value=other)

    def __ne__(self, other: Any) -> EqualsNot:
        return EqualsNot(prop=self, value=other)

    def __gt__(self, value: Any) -> GreaterThan:
        return GreaterThan(prop=self, value=value)

    def __lt__(self, value: Any) -> LessThan:
        return LessThan(prop=self, value=value)

    def __ge__(self, value: Any) -> GreaterThanOrEqualTo:
        return GreaterThanOrEqualTo(prop=self, value=value)

    def __le__(self, value: Any) -> LessThanOrEqualTo:
        return LessThanOrEqualTo(prop=self, value=value)

    def contains(self, value: str) -> Contains:
        return Contains(prop=self, value=value)

    def does_not_contain(self, value: str) -> ContainsNot:
        return ContainsNot(prop=self, value=value)

    def starts_with(self, value: str) -> StartsWith:
        return StartsWith(prop=self, value=value)

    def ends_with(self, value: str) -> EndsWith:
        return EndsWith(prop=self, value=value)

    def is_empty(self) -> IsEmpty:
        return IsEmpty(prop=self)

    def is_not_empty(self) -> IsNotEmpty:
        return IsNotEmpty(prop=self)

    def before(self, value: dt.datetime) -> Before:
        return Before(prop=self, value=value)

    def after(self, value: dt.datetime) -> After:
        return After(prop=self, value=value)

    def on_or_before(self, value: dt.datetime) -> OnOrBefore:
        return OnOrBefore(prop=self, value=value)

    def on_or_after(self, value: dt.datetime) -> OnOrAfter:
        return OnOrAfter(prop=self, value=value)

    def this_week(self) -> ThisWeek:
        return ThisWeek(prop=self)

    def past_week(self) -> PastWeek:
        return PastWeek(prop=self)

    def past_month(self) -> PastMonth:
        return PastMonth(prop=self)

    def past_year(self) -> PastYear:
        return PastYear(prop=self)

    def next_week(self) -> NextWeek:
        return NextWeek(prop=self)

    def next_month(self) -> NextMonth:
        return NextMonth(prop=self)

    def next_year(self) -> NextYear:
        return NextYear(prop=self)

    def asc(self) -> Self:
        self.sort_direction = SortDirection.ASCENDING
        return self

    def desc(self) -> Self:
        self.sort_direction = SortDirection.DESCENDING
        return self

    def __repr__(self) -> str:
        return f"prop('{self.prop_name}')"

    def __str__(self) -> str:
        return repr(self)


# ToDo: Also add last_edited_time, created_time, filters


def prop(prop_name: str, /) -> Property:
    """Create a column object."""
    return Property(prop_name=prop_name)


class Condition(BaseModel, ABC):
    """Base class for filter query conditions."""

    def __and__(self, other: Condition) -> Condition:
        return And(left=self, right=other)

    def __or__(self, other: Condition) -> Condition:
        return Or(left=self, right=other)

    @abstractmethod
    def __repr__(self) -> str: ...

    def __str__(self) -> str:
        return repr(self)


class Equals(Condition):
    prop: Property
    value: Any

    _conditions = ()

    def serialize_for_api(self, db: Database) -> dict[str, Any]:
        prop_type = db.schema[self.prop.prop_name]
        kwargs = {'property': self.prop.prop_name}
        match prop_type:
            case schema.Text() | schema.Title() | schema.PhoneNumber():
                kwargs['rich_text'] = obj_query.TextCondition(equals=self.value)
            case schema.Number(_):
                kwargs['number'] = obj_query.NumberCondition(equals=self.value)
            case schema.Select():
                kwargs['select'] = obj_query.SelectCondition(equals=str(self.value))
            case schema.MultiSelect():
                kwargs['multi_select'] = obj_query.MultiSelectCondition(equals=str(self.value))
            case schema.Date():
                kwargs['date'] = obj_query.DateCondition(equals=self.value)
            case schema.Checkbox():
                kwargs['checkbox'] = obj_query.CheckboxCondition(equals=bool(self.value))
            case schema.Formula(_):
                # ToDo: Match the type here.
                kwargs['formula'] = obj_query.FormulaCondition(equals=self.value)
            case _:
                msg = f'Unsupported property type `{prop_type}` for == condition.'
                raise ValueError(msg)
        obj_filter = obj_query.PropertyFilter(**kwargs)
        return obj_filter.serialize_for_api()

    def __repr__(self) -> str:
        return f'({self.prop} == {self.value})'


class EqualsNot(Condition):
    prop: Property
    value: Any

    def __repr__(self) -> str:
        return f'({self.prop} != {self.value})'


class Contains(Condition):
    prop: Property
    value: Any

    def __repr__(self) -> str:
        return f'{self.prop}.contains({self.value})'


class ContainsNot(Condition):
    prop: Property
    value: str

    def __repr__(self) -> str:
        return f'{self.prop}.does_not_contain({self.value})'


class StartsWith(Condition):
    prop: Property
    value: str

    def __repr__(self) -> str:
        return f'{self.prop}.starts_with({self.value})'


class EndsWith(Condition):
    prop: Property
    value: str

    def __repr__(self) -> str:
        return f'{self.prop}.ends_with({self.value})'


class IsEmpty(Condition):
    prop: Property

    def __repr__(self) -> str:
        return f"{self.prop} == ''"


class IsNotEmpty(Condition):
    prop: Property

    def __repr__(self) -> str:
        return f"{self.prop} != ''"


class GreaterThan(Condition):
    prop: Property
    value: Any

    def __repr__(self) -> str:
        return f'({self.prop} > {self.value})'


class LessThan(Condition):
    prop: Property
    value: Any

    def __repr__(self) -> str:
        return f'({self.prop} < {self.value})'


class GreaterThanOrEqualTo(Condition):
    prop: Property
    value: Any

    def __repr__(self) -> str:
        return f'({self.prop} >= {self.value})'


class LessThanOrEqualTo(Condition):
    prop: Property
    value: Any

    def __repr__(self) -> str:
        return f'({self.prop} <= {self.value})'


class Before(Condition):
    prop: Property
    value: Any

    def __repr__(self) -> str:
        return f'({self.prop} < {self.value})'


class After(Condition):
    prop: Property
    value: Any

    def __repr__(self) -> str:
        return f'({self.prop} > {self.value})'


class OnOrBefore(Condition):
    prop: Property
    value: Any

    def __repr__(self) -> str:
        return f'({self.prop} <= {self.value})'


class OnOrAfter(Condition):
    prop: Property
    value: Any

    def __repr__(self) -> str:
        return f'({self.prop} >= {self.value})'


class PastWeek(Condition):
    prop: Property

    def __repr__(self) -> str:
        return f'{self.prop}.past_week()'


class PastMonth(Condition):
    prop: Property

    def __repr__(self) -> str:
        return f'{self.prop}.past_month()'


class PastYear(Condition):
    prop: Property

    def __repr__(self) -> str:
        return f'{self.prop}.past_year()'


class ThisWeek(Condition):
    prop: Property

    def __repr__(self) -> str:
        return f'{self.prop}.this_week()'


class NextWeek(Condition):
    prop: Property

    def __repr__(self) -> str:
        return f'{self.prop}.next_week()'


class NextMonth(Condition):
    prop: Property

    def __repr__(self) -> str:
        return f'{self.prop}.next_month()'


class NextYear(Condition):
    prop: Property

    def __repr__(self) -> str:
        return f'{self.prop}.next_year()'


class And(Condition):
    left: Condition
    right: Condition

    def __repr__(self) -> str:
        return f'({self.left} AND {self.right})'


class Or(Condition):
    left: Condition
    right: Condition

    def __repr__(self) -> str:
        return f'({self.left} OR {self.right})'


class Query:
    """A query object to filter and sort pages in a database."""

    _filter: Condition | None = None
    _sorts: list[Property] | None = None

    def __init__(self, database: Database):
        self.database = database

    def execute(self) -> View:
        """Execute the query and return the resulting pages as a view."""
        session = get_active_session()
        query_obj = session.api.databases.query(self.database.obj_ref)
        if self._filter:
            query_obj.filter(self._filter.serialize_for_api(self.database))
        if self._sorts:
            query_obj.sort(
                [obj_query.DBSort(property=prop.prop_name, direction=prop.sort_direction) for prop in self._sorts]
            )
        pages = [cast(Page, session.cache.setdefault(page.id, Page.wrap_obj_ref(page))) for page in query_obj.execute()]
        return View(database=self.database, pages=pages, query=self)

    def filter(self, expr: Condition) -> Query:
        """Filter the query by the given properties.

        !!! note
            The filter is applied as an AND operation with the existing filter.
        """
        if self._filter is None:
            self._filter = expr
        else:
            self._filter &= expr
        return self

    def sort(self, *props: Property | str) -> Query:
        """Sort the query by the given properties and directions.

        !!! note
            The order of the properties is important. The first property is the primary sort,
            the second is the secondary sort, and so on. Calling this method multiple times
            will overwrite the previous sorts.
        """
        self._sorts = [prop if isinstance(prop, Property) else Property(prop) for prop in props]
        return self

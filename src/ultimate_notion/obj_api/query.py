"""Provides an interactive query builder for Notion databases."""

from __future__ import annotations

import logging
from abc import ABC
from collections.abc import Awaitable, Callable, Iterator, Mapping
from datetime import date, datetime
from typing import Any, Generic, Literal, TypeAlias
from uuid import UUID

from pydantic import ConfigDict, Field, SerializeAsAny, field_validator
from typing_extensions import TypeVar

from ultimate_notion.obj_api.blocks import Database, Page
from ultimate_notion.obj_api.core import GenericObject
from ultimate_notion.obj_api.enums import SortDirection, TimestampKind
from ultimate_notion.obj_api.iterator import MAX_PAGE_SIZE, EndpointIterator

NCEndpointCall: TypeAlias = Callable[..., Any | Awaitable[Any]]  # ToDo: `type` instead of `TypeAlias` in Python 3.12

_logger = logging.getLogger(__name__)


class Condition(GenericObject, ABC):
    """Base class for all conditions in Notion."""


class TextCondition(Condition):
    """Represents text criteria in Notion."""

    equals: str | None = None
    does_not_equal: str | None = None
    contains: str | None = None
    does_not_contain: str | None = None
    starts_with: str | None = None
    ends_with: str | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class NumberCondition(Condition):
    """Represents number criteria in Notion."""

    equals: float | int | None = None
    does_not_equal: float | int | None = None
    greater_than: float | int | None = None
    less_than: float | int | None = None
    greater_than_or_equal_to: float | int | None = None
    less_than_or_equal_to: float | int | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class IdCondition(Condition):
    """Represents ID criteria in Notion."""

    equals: float | int | None = None
    does_not_equal: float | int | None = None
    greater_than: float | int | None = None
    less_than: float | int | None = None
    greater_than_or_equal_to: float | int | None = None
    less_than_or_equal_to: float | int | None = None


class CheckboxCondition(Condition):
    """Represents checkbox criteria in Notion."""

    equals: bool | None = None
    does_not_equal: bool | None = None


class SelectCondition(Condition):
    """Represents select criteria in Notion."""

    equals: str | None = None
    does_not_equal: str | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class MultiSelectCondition(Condition):
    """Represents a multi_select criteria in Notion."""

    contains: str | None = None
    does_not_contain: str | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class DateCondition(Condition):
    """Represents date criteria in Notion."""

    equals: date | datetime | None = None
    before: date | datetime | None = None
    after: date | datetime | None = None
    on_or_before: date | datetime | None = None
    on_or_after: date | datetime | None = None

    is_empty: bool | None = None
    is_not_empty: bool | None = None

    class EmptyObject(GenericObject): ...

    this_week: EmptyObject | None = None
    past_week: EmptyObject | None = None
    past_month: EmptyObject | None = None
    past_year: EmptyObject | None = None
    next_week: EmptyObject | None = None
    next_month: EmptyObject | None = None
    next_year: EmptyObject | None = None


class PeopleCondition(Condition):
    """Represents people criteria in Notion."""

    contains: UUID | None = None
    does_not_contain: UUID | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class FilesCondition(Condition):
    """Represents files criteria in Notion."""

    is_empty: bool | None = None
    is_not_empty: bool | None = None


class RelationCondition(Condition):
    """Represents relation criteria in Notion."""

    contains: UUID | None = None
    does_not_contain: UUID | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class FormulaCondition(Condition):
    """Represents formula criteria in Notion."""

    string: TextCondition | None = None
    checkbox: CheckboxCondition | None = None
    number: NumberCondition | None = None
    date: DateCondition | None = None


class RollupArrayCondition(Condition):
    """Represents a rollup array filter in Notion."""

    rich_text: TextCondition | None = None
    phone_number: TextCondition | None = None
    number: NumberCondition | None = None
    checkbox: CheckboxCondition | None = None
    select: SelectCondition | None = None
    multi_select: MultiSelectCondition | None = None
    date: DateCondition | None = None
    people: PeopleCondition | None = None
    files: FilesCondition | None = None
    relation: RelationCondition | None = None
    formula: FormulaCondition | None = None
    unique_id: IdCondition | None = None


class RollupCondition(Condition):
    """Represents rollup criteria in Notion."""

    any: RollupArrayCondition | None = None
    every: RollupArrayCondition | None = None
    none: RollupArrayCondition | None = None
    date: DateCondition | None = None
    number: NumberCondition | None = None


class QueryFilter(GenericObject):
    """Base class for query filters."""


class PropertyFilter(QueryFilter, RollupArrayCondition):
    """Represents a database property filter in Notion."""

    property: str
    rollup: RollupCondition | None = None


class SearchFilter(QueryFilter):
    """Represents a search property filter in Notion."""

    property: str
    value: str


class TimestampFilter(QueryFilter):
    """Represents a timestamp filter in Notion."""

    timestamp: TimestampKind


class CreatedTimeFilter(TimestampFilter):
    """Represents a created_time filter in Notion."""

    created_time: DateCondition
    timestamp: TimestampKind = TimestampKind.CREATED_TIME


class LastEditedTimeFilter(TimestampFilter):
    """Represents a last_edited_time filter in Notion."""

    last_edited_time: DateCondition
    timestamp: TimestampKind = TimestampKind.LAST_EDITED_TIME


class CompoundFilter(QueryFilter):
    """Represents a compound filter in Notion."""

    model_config = ConfigDict(populate_by_name=True)

    and_: list[SerializeAsAny[QueryFilter]] | None = Field(None, alias='and')
    or_: list[SerializeAsAny[QueryFilter]] | None = Field(None, alias='or')


class DBSort(GenericObject):
    """Sort instruction when querying a database"""

    property: str
    direction: SortDirection


class SearchSort(GenericObject):
    """Sort instruction when searching for pages and databases"""

    timestamp: Literal[TimestampKind.LAST_EDITED_TIME]
    direction: SortDirection


class Query(GenericObject, ABC):
    """Abstract query object in Notion for searching pages/databases and querying databases"""

    filter: SerializeAsAny[QueryFilter] | None = None
    start_cursor: UUID | None = None
    page_size: int = MAX_PAGE_SIZE

    @field_validator('page_size')
    @classmethod
    def valid_page_size(cls, value: int) -> int:
        """Validate that the given page size meets the Notion API requirements"""

        if value <= 0:
            msg = 'page size must be greater than zero'
            raise ValueError(msg)
        if value > MAX_PAGE_SIZE:
            msg = f'page size must be less than or equal to {MAX_PAGE_SIZE}'
            raise ValueError(msg)

        return value


class SearchQuery(Query):
    """Query object in Notion for searching pages & databases"""

    sort: SearchSort | None = None


class DBQuery(Query):
    """Query object in Notion for querying a database"""

    sorts: list[DBSort] | None = None


T = TypeVar('T', bound=Page | Database, default=Page | Database)


class QueryBuilder(Generic[T], ABC):
    """General query builder for the Notion search & database query API"""

    query: Query
    endpoint: NCEndpointCall
    params: dict[str, str]

    def __init__(self, endpoint: NCEndpointCall, query: Query, params: Mapping[str, str | None]):
        self.endpoint = endpoint
        self.query = query
        self.params = {k: v for k, v in params.items() if v is not None}  # API doesn't like "undefined" values

    def execute(self, **nc_params: int | str) -> Iterator[T]:
        """Execute the current query and return an iterator for the results."""
        query = self.query.serialize_for_api()
        query |= self.params | nc_params
        return EndpointIterator[T](self.endpoint)(**query)


class SearchQueryBuilder(QueryBuilder[T]):
    """Search query builder to search for pages and databases

    By default and not changed by `sort`, then the most recently edited results are returned first.

    Notion API: https://developers.notion.com/reference/post-search
    """

    query: SearchQuery

    def __init__(self, endpoint: NCEndpointCall, text: str | None = None):
        super().__init__(endpoint=endpoint, query=SearchQuery(), params={'query': text})

    def execute(self, **nc_params: int | str) -> Iterator[T]:
        match self.filter:
            case SearchFilter(property='object', value='page'):
                _logger.debug(f'Searching for pages with title: {self.params["query"]}')
            case SearchFilter(property='object', value='database'):
                _logger.debug(f'Searching for databases with title: {self.params["query"]}')
            case None:
                _logger.debug(f'Searching for pages and databases with title: {self.params["query"]}')
        return super().execute(**nc_params)

    def filter(self, *, page_only: bool = False, db_only: bool = False) -> SearchQueryBuilder[T]:
        """Filter for pages or databases only"""
        if not (page_only ^ db_only):
            msg = 'Either `page_only` or `db_only` must be true, not both.'
            raise ValueError(msg)
        elif page_only:
            value = 'page'
        else:  # db_only
            value = 'database'

        builder = SearchQueryBuilder[T](self.endpoint, text=self.params.get('query'))
        builder.query.filter = SearchFilter(property='object', value=value)
        return builder

    def sort(self, *, ascending: bool) -> SearchQueryBuilder[T]:
        """Add the given sort elements to the query."""
        direction = SortDirection.ASCENDING if ascending else SortDirection.DESCENDING

        builder = SearchQueryBuilder[T](self.endpoint, text=self.params.get('query'))
        builder.query.sort = SearchSort(timestamp=TimestampKind.LAST_EDITED_TIME, direction=direction)
        return builder


class DBQueryBuilder(QueryBuilder[Page]):
    """Query builder to query a database.

    Notion API: https://developers.notion.com/reference/post-search
    """

    query: DBQuery

    def __init__(self, endpoint: NCEndpointCall, db_id: str):
        super().__init__(endpoint=endpoint, query=DBQuery(), params={'database_id': db_id})

    def execute(self, **nc_params: int | str) -> Iterator[Page]:
        _logger.debug(f'Searching for pages in database with id: {self.params["database_id"]}')
        return super().execute(**nc_params)

    def filter(self, condition: QueryFilter) -> DBQueryBuilder:
        """Add the given filter to the query."""
        builder = DBQueryBuilder(self.endpoint, db_id=self.params['database_id'])
        if self.query.sorts is not None:
            builder.query.sorts = [sort.model_copy(deep=True) for sort in self.query.sorts]
        builder.query.filter = condition
        return builder

    def sort(self, sort_orders: DBSort | list[DBSort]) -> DBQueryBuilder:
        """Add the given sort elements to the query."""
        if isinstance(sort_orders, DBSort):
            sort_orders = [sort_orders]

        builder = DBQueryBuilder(self.endpoint, db_id=self.params['database_id'])
        if self.query.filter is not None:
            builder.query.filter = self.query.filter.model_copy(deep=True)
        builder.query.sorts = sort_orders
        return builder

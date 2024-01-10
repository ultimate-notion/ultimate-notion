"""Provides an interactive query builder for Notion databases."""

from __future__ import annotations

import logging
from abc import ABC
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, SerializeAsAny, field_validator

from ultimate_notion.obj_api.core import GenericObject
from ultimate_notion.obj_api.iterator import MAX_PAGE_SIZE, EndpointIterator

if TYPE_CHECKING:
    from notion_client.api_endpoints import Endpoint as NCEndpoint

logger = logging.getLogger(__name__)


class TextCondition(GenericObject):
    """Represents text criteria in Notion."""

    equals: str | None = None
    does_not_equal: str | None = None
    contains: str | None = None
    does_not_contain: str | None = None
    starts_with: str | None = None
    ends_with: str | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class NumberCondition(GenericObject):
    """Represents number criteria in Notion."""

    equals: float | int | None = None
    does_not_equal: float | int | None = None
    greater_than: float | int | None = None
    less_than: float | int | None = None
    greater_than_or_equal_to: float | int | None = None
    less_than_or_equal_to: float | int | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class CheckboxCondition(GenericObject):
    """Represents checkbox criteria in Notion."""

    equals: bool | None = None
    does_not_equal: bool | None = None


class SelectCondition(GenericObject):
    """Represents select criteria in Notion."""

    equals: str | None = None
    does_not_equal: str | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class MultiSelectCondition(GenericObject):
    """Represents a multi_select criteria in Notion."""

    contains: str | None = None
    does_not_contains: str | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class DateCondition(GenericObject):
    """Represents date criteria in Notion."""

    equals: date | datetime | None = None
    before: date | datetime | None = None
    after: date | datetime | None = None
    on_or_before: date | datetime | None = None
    on_or_after: date | datetime | None = None

    is_empty: bool | None = None
    is_not_empty: bool | None = None

    past_week: Any | None = None
    past_month: Any | None = None
    past_year: Any | None = None
    next_week: Any | None = None
    next_month: Any | None = None
    next_year: Any | None = None


class PeopleCondition(GenericObject):
    """Represents people criteria in Notion."""

    contains: UUID | None = None
    does_not_contain: UUID | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class FilesCondition(GenericObject):
    """Represents files criteria in Notion."""

    is_empty: bool | None = None
    is_not_empty: bool | None = None


class RelationCondition(GenericObject):
    """Represents relation criteria in Notion."""

    contains: UUID | None = None
    does_not_contain: UUID | None = None
    is_empty: bool | None = None
    is_not_empty: bool | None = None


class FormulaCondition(GenericObject):
    """Represents formula criteria in Notion."""

    string: TextCondition | None = None
    checkbox: CheckboxCondition | None = None
    number: NumberCondition | None = None
    date: DateCondition | None = None


class QueryFilter(GenericObject):
    """Base class for query filters."""


class PropertyFilter(QueryFilter):
    """Represents a database property filter in Notion."""

    property: str

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


class SearchFilter(QueryFilter):
    """Represents a search property filter in Notion."""

    property: str
    value: str


class TimestampKind(str, Enum):
    """Possible timestamp types."""

    CREATED_TIME = 'created_time'
    LAST_EDITED_TIME = 'last_edited_time'


class TimestampFilter(QueryFilter):
    """Represents a timestamp filter in Notion."""

    timestamp: TimestampKind


class CreatedTimeFilter(TimestampFilter):
    """Represents a created_time filter in Notion."""

    created_time: DateCondition
    timestamp: TimestampKind = TimestampKind.CREATED_TIME

    @classmethod
    def build(cls, value):
        """Create a new `CreatedTimeFilter` using the given constraint."""
        return CreatedTimeFilter(created_time=value)


class LastEditedTimeFilter(TimestampFilter):
    """Represents a last_edited_time filter in Notion."""

    last_edited_time: DateCondition
    timestamp: TimestampKind = TimestampKind.LAST_EDITED_TIME

    @classmethod
    def build(cls, value):
        """Create a new `LastEditedTimeFilter` using the given constraint."""
        return LastEditedTimeFilter(last_edited_time=value)


class CompoundFilter(QueryFilter):
    """Represents a compound filter in Notion."""

    # ToDo: Split this up in a And and Or Filter

    model_config = ConfigDict(populate_by_name=True)

    and_: list[QueryFilter] | None = Field(None, alias='and')
    or_: list[QueryFilter] | None = Field(None, alias='or')


class SortDirection(str, Enum):
    """Sort direction options."""

    ASCENDING = 'ascending'
    DESCENDING = 'descending'


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


class QueryBuilder(ABC):
    """General query builder for the Notion search & database query API"""

    query: Query
    endpoint: NCEndpoint
    params: dict[str, str]

    def __init__(self, endpoint: NCEndpoint, **params: str | None):
        self.endpoint = endpoint
        self.params = {param: value for param, value in params.items() if value is not None}

    def start_at(self, cursor_id: UUID):
        """Set the start cursor to a specific page ID."""

        self.query.start_cursor = cursor_id
        return self

    def limit(self, count: int):
        """Limit the number of results to the given count."""

        self.query.page_size = count
        return self

    def execute(self):
        """Execute the current query and return an iterator for the results."""
        logger.debug('executing query - %s', self.query)

        # the API doesn't like "undefined" values...
        query = self.query.serialize_for_api()

        if self.params:
            query.update(self.params)

        return EndpointIterator(self.endpoint)(**query)

    def first(self):
        """Execute the current query and return the first result only."""

        try:
            return next(self.execute())
        except StopIteration:
            logger.debug('iterator returned empty result set')


class SearchQueryBuilder(QueryBuilder):
    """Search query builder to search for pages and databases

    By default and not changed by `sort`, then the most recently edited results are returned first.

    Notion API: https://developers.notion.com/reference/post-search
    """

    query: SearchQuery

    def __init__(self, endpoint, text: str | None = None):
        self.query = SearchQuery()
        super().__init__(endpoint=endpoint, query=text)

    def filter(self, *, page_only: bool = False, db_only: bool = False) -> SearchQueryBuilder:
        """Filter for pages or databases only"""
        if not (page_only ^ db_only):
            msg = 'Either `page_only` or `db_only` must be true, not both.'
            raise ValueError(msg)
        elif page_only:
            value = 'page'
        else:  # db_only
            value = 'database'

        self.query.filter = SearchFilter(property='object', value=value)
        return self

    def sort(self, *, ascending: bool) -> SearchQueryBuilder:
        """Add the given sort elements to the query."""
        direction = SortDirection.ASCENDING if ascending else SortDirection.DESCENDING
        self.query.sort = SearchSort(timestamp=TimestampKind.LAST_EDITED_TIME, direction=direction)
        return self


class DBQueryBuilder(QueryBuilder):
    """Query builder to query a database.

    Notion API: https://developers.notion.com/reference/post-search
    """

    query: DBQuery

    def __init__(self, endpoint, db_id: str):
        self.query = DBQuery()
        super().__init__(endpoint=endpoint, database_id=db_id)

    def filter(self, condition: QueryFilter) -> DBQueryBuilder:
        """Add the given filter to the query."""
        self.query.filter = condition
        return self

    def sort(self, sort_orders: DBSort | list[DBSort]) -> DBQueryBuilder:
        """Add the given sort elements to the query."""
        if isinstance(sort_orders, DBSort):
            sort_orders = [sort_orders]

        self.query.sorts = sort_orders
        return self

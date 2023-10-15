"""Provides an interactive query builder for Notion databases."""
from __future__ import annotations

import logging
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from notion_client.api_endpoints import SearchEndpoint
from pydantic import Field, SerializeAsAny, field_validator

from ultimate_notion.obj_api.core import GenericObject
from ultimate_notion.obj_api.iterator import MAX_PAGE_SIZE, EndpointIterator

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

    property: str  # noqa: A003

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

    property: str  # noqa: A003
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


class CompoundFilter(QueryFilter, populate_by_name=True):
    """Represents a compound filter in Notion."""

    and_: list[QueryFilter] | None = Field(None, alias='and')
    or_: list[QueryFilter] | None = Field(None, alias='or')


class SortDirection(str, Enum):
    """Sort direction options."""

    ASCENDING = 'ascending'
    DESCENDING = 'descending'


class PropertySort(GenericObject):
    """Represents a sort instruction in Notion."""

    property: str | None = None  # noqa: A003
    timestamp: TimestampKind | None = None
    direction: SortDirection | None = None


class Query(GenericObject):
    """Represents a query object in Notion."""

    sorts: list[PropertySort] | None = None
    filter: SerializeAsAny[QueryFilter] | None = None  # noqa: A003
    start_cursor: UUID | None = None
    page_size: int = MAX_PAGE_SIZE

    @field_validator('page_size')
    @classmethod
    @classmethod
    def valid_page_size(cls, value):
        """Validate that the given page size meets the Notion API requirements."""

        if value <= 0:
            msg = 'page size must be greater than zero'
            raise ValueError(msg)
        if value > MAX_PAGE_SIZE:
            msg = f'page size must be less than or equal to {MAX_PAGE_SIZE}'
            raise ValueError(msg)

        return value


class QueryBuilder:
    """A query builder for the Notion API.

    :param endpoint: the session endpoint used to execute the query
    :param datatype: an optional class to capture results
    :param params: optional params that will be passed to the query
    """

    def __init__(self, endpoint, datatype=None, **params):
        """Initialize a new `QueryBuilder` for the given endpoint."""

        self.endpoint = endpoint
        self.datatype = datatype  # ToDo: See if this is really needed or if we can get rid of it!
        self.params = params

        self.query = Query()

    def filter(self, query_filter=None, **kwargs):  # noqa: A003
        """Add the given filter to the query."""

        if query_filter is None:
            if isinstance(self.endpoint, SearchEndpoint):
                query_filter = SearchFilter.model_validate(kwargs)
            elif 'property' in kwargs:
                query_filter = PropertyFilter.model_validate(kwargs)
            elif 'timestamp' in kwargs and kwargs['timestamp'] == 'created_time':
                query_filter = CreatedTimeFilter.model_validate(kwargs)
            elif 'timestamp' in kwargs and kwargs['timestamp'] == 'last_edited_time':
                query_filter = LastEditedTimeFilter.model_validate(kwargs)
            else:
                msg = 'unrecognized filter'
                raise ValueError(msg)

        elif not isinstance(query_filter, QueryFilter):
            msg = 'filter must be of type QueryFilter'
            raise ValueError(msg)

        # use CompoundFilter when necessary...

        if self.query.filter is None:
            self.query.filter = query_filter

        elif isinstance(self.query.filter, CompoundFilter):
            self.query.filter.and_.append(query_filter)

        else:
            old_filter = self.query.filter
            self.query.filter = CompoundFilter(and_=[old_filter, query_filter])

        return self

    def sort(self, sort=None, **kwargs):
        """Add the given sort elements to the query."""

        if sort is None:
            sort = PropertySort(**kwargs)

        elif not isinstance(filter, PropertySort):
            msg = 'sort must be of type PropertySort'
            raise ValueError(msg)

        # use multiple sorts when necessary

        if self.query.sorts is None:
            self.query.sorts = [sort]

        else:
            self.query.sorts.append(sort)

        return self

    def start_at(self, page_id):
        """Set the start cursor to a specific page ID."""

        self.query.start_cursor = page_id

        return self

    def limit(self, count):
        """Limit the number of results to the given count."""

        self.query.page_size = count

        return self

    def execute(self):
        """Execute the current query and return an iterator for the results."""

        if self.endpoint is None:
            msg = 'cannot execute query; no endpoint provided'
            raise ValueError(msg)

        logger.debug('executing query - %s', self.query)

        # the API doesn't like "undefined" values...
        query = self.query.serialize_for_api()

        if self.params:
            query.update(self.params)

        return EndpointIterator(self.endpoint, datatype=self.datatype)(**query)

    def first(self):
        """Execute the current query and return the first result only."""

        try:
            return next(self.execute())
        except StopIteration:
            logger.debug('iterator returned empty result set')

        return None

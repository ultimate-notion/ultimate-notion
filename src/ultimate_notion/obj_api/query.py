"""Provides an interactive query builder for Notion databases."""

import logging
from datetime import date, datetime
from enum import Enum
from typing import Any, List, Optional, Union
from uuid import UUID

from notion_client.api_endpoints import SearchEndpoint
from pydantic import Field, validator

from ultimate_notion.obj_api.core import GenericObject
from ultimate_notion.obj_api.iterator import MAX_PAGE_SIZE, EndpointIterator

logger = logging.getLogger(__name__)


class TextCondition(GenericObject):
    """Represents text criteria in Notion."""

    equals: Optional[str] = None
    does_not_equal: Optional[str] = None
    contains: Optional[str] = None
    does_not_contain: Optional[str] = None
    starts_with: Optional[str] = None
    ends_with: Optional[str] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class NumberCondition(GenericObject):
    """Represents number criteria in Notion."""

    equals: Optional[Union[float, int]] = None
    does_not_equal: Optional[Union[float, int]] = None
    greater_than: Optional[Union[float, int]] = None
    less_than: Optional[Union[float, int]] = None
    greater_than_or_equal_to: Optional[Union[float, int]] = None
    less_than_or_equal_to: Optional[Union[float, int]] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class CheckboxCondition(GenericObject):
    """Represents checkbox criteria in Notion."""

    equals: Optional[bool] = None
    does_not_equal: Optional[bool] = None


class SelectCondition(GenericObject):
    """Represents select criteria in Notion."""

    equals: Optional[str] = None
    does_not_equal: Optional[str] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class MultiSelectCondition(GenericObject):
    """Represents a multi_select criteria in Notion."""

    contains: Optional[str] = None
    does_not_contains: Optional[str] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class DateCondition(GenericObject):
    """Represents date criteria in Notion."""

    equals: Optional[Union[date, datetime]] = None
    before: Optional[Union[date, datetime]] = None
    after: Optional[Union[date, datetime]] = None
    on_or_before: Optional[Union[date, datetime]] = None
    on_or_after: Optional[Union[date, datetime]] = None

    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None

    past_week: Optional[Any] = None
    past_month: Optional[Any] = None
    past_year: Optional[Any] = None
    next_week: Optional[Any] = None
    next_month: Optional[Any] = None
    next_year: Optional[Any] = None


class PeopleCondition(GenericObject):
    """Represents people criteria in Notion."""

    contains: Optional[UUID] = None
    does_not_contain: Optional[UUID] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class FilesCondition(GenericObject):
    """Represents files criteria in Notion."""

    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class RelationCondition(GenericObject):
    """Represents relation criteria in Notion."""

    contains: Optional[UUID] = None
    does_not_contain: Optional[UUID] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class FormulaCondition(GenericObject):
    """Represents formula criteria in Notion."""

    string: Optional[TextCondition] = None
    checkbox: Optional[CheckboxCondition] = None
    number: Optional[NumberCondition] = None
    date: Optional[DateCondition] = None


class QueryFilter(GenericObject):
    """Base class for query filters."""


class PropertyFilter(QueryFilter):
    """Represents a database property filter in Notion."""

    property: str

    rich_text: Optional[TextCondition] = None
    phone_number: Optional[TextCondition] = None
    number: Optional[NumberCondition] = None
    checkbox: Optional[CheckboxCondition] = None
    select: Optional[SelectCondition] = None
    multi_select: Optional[MultiSelectCondition] = None
    date: Optional[DateCondition] = None
    people: Optional[PeopleCondition] = None
    files: Optional[FilesCondition] = None
    relation: Optional[RelationCondition] = None
    formula: Optional[FormulaCondition] = None


class SearchFilter(QueryFilter):
    """Represents a search property filter in Notion."""

    property: str
    value: str


class TimestampKind(str, Enum):
    """Possible timestamp types."""

    CREATED_TIME = "created_time"
    LAST_EDITED_TIME = "last_edited_time"


class TimestampFilter(QueryFilter):
    """Represents a timestamp filter in Notion."""

    timestamp: TimestampKind


class CreatedTimeFilter(TimestampFilter):
    """Represents a created_time filter in Notion."""

    created_time: DateCondition
    timestamp: TimestampKind = TimestampKind.CREATED_TIME

    @classmethod
    def __compose__(cls, value):
        """Create a new `CreatedTimeFilter` using the given constraint."""
        return CreatedTimeFilter(created_time=value)


class LastEditedTimeFilter(TimestampFilter):
    """Represents a last_edited_time filter in Notion."""

    last_edited_time: DateCondition
    timestamp: TimestampKind = TimestampKind.LAST_EDITED_TIME

    @classmethod
    def __compose__(cls, value):
        """Create a new `LastEditedTimeFilter` using the given constraint."""
        return LastEditedTimeFilter(last_edited_time=value)


class CompoundFilter(QueryFilter):
    """Represents a compound filter in Notion."""

    class Config:
        """Pydantic configuration class to support keyword fields."""

        allow_population_by_field_name = True

    and_: Optional[List[QueryFilter]] = Field(None, alias="and")
    or_: Optional[List[QueryFilter]] = Field(None, alias="or")


class SortDirection(str, Enum):
    """Sort direction options."""

    ASCENDING = "ascending"
    DESCENDING = "descending"


class PropertySort(GenericObject):
    """Represents a sort instruction in Notion."""

    property: Optional[str] = None
    timestamp: Optional[TimestampKind] = None
    direction: Optional[SortDirection] = None


class Query(GenericObject):
    """Represents a query object in Notion."""

    sorts: Optional[List[PropertySort]] = None
    filter: Optional[QueryFilter] = None
    start_cursor: Optional[UUID] = None
    page_size: int = MAX_PAGE_SIZE

    @validator("page_size")
    def valid_page_size(cls, value):
        """Validate that the given page size meets the Notion API requirements."""

        assert value > 0, "size must be greater than zero"
        assert value <= MAX_PAGE_SIZE, "size must be less than or equal to 100"

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
        self.datatype = datatype
        self.params = params

        self.query = Query()

    def filter(self, filter=None, **kwargs):
        """Add the given filter to the query."""

        if filter is None:
            if isinstance(self.endpoint, SearchEndpoint):
                filter = SearchFilter.parse_obj(kwargs)
            elif "property" in kwargs:
                filter = PropertyFilter.parse_obj(kwargs)
            elif "timestamp" in kwargs and kwargs["timestamp"] == "created_time":
                filter = CreatedTimeFilter.parse_obj(kwargs)
            elif "timestamp" in kwargs and kwargs["timestamp"] == "last_edited_time":
                filter = LastEditedTimeFilter.parse_obj(kwargs)
            else:
                raise ValueError("unrecognized filter")

        elif not isinstance(filter, QueryFilter):
            raise ValueError("filter must be of type QueryFilter")

        # use CompoundFilter when necessary...

        if self.query.filter is None:
            self.query.filter = filter

        elif isinstance(self.query.filter, CompoundFilter):
            self.query.filter.and_.append(filter)

        else:
            old_filter = self.query.filter
            self.query.filter = CompoundFilter(and_=[old_filter, filter])

        return self

    def sort(self, sort=None, **kwargs):
        """Add the given sort elements to the query."""

        # XXX should this support ORM properties also?
        # e.g. - query.sort(property=Task.Title)
        # but users won't always use ORM for queries...

        if sort is None:
            sort = PropertySort(**kwargs)

        elif not isinstance(filter, PropertySort):
            raise ValueError("sort must be of type PropertySort")

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
            raise ValueError("cannot execute query; no endpoint provided")

        logger.debug("executing query - %s", self.query)

        query = self.query.dict()

        if self.params:
            query.update(self.params)

        return EndpointIterator(self.endpoint, datatype=self.datatype)(**query)

    def first(self):
        """Execute the current query and return the first result only."""

        try:
            return next(self.execute())
        except StopIteration:
            logger.debug("iterator returned empty result set")

        return None

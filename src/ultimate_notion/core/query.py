"""Provides an interactive query builder for Notion databases."""

import logging
from datetime import date, datetime
from enum import Enum
from inspect import isclass
from typing import Any, List, Optional, Union
from uuid import UUID

from notion_client.api_endpoints import SearchEndpoint
from pydantic import Field, validator

from .bases import DataObject
from .blocks import Block
from .iterator import EndpointIterator
from .orm import ConnectedPage
from .records import Database, Page, ParentRef, Record

_log = logging.getLogger(__name__)


def get_target_id(target):
    """Examine the given target and returns the appropriate ID as a string."""

    if isinstance(target, str):
        return target

    if isinstance(target, UUID):
        return target.hex

    if isinstance(target, Record):
        return target.id.hex

    if isinstance(target, ParentRef):
        return target().hex

    if isclass(target) and issubclass(target, ConnectedPage):
        return target._notional__database

    raise ValueError("unsupported query target")


class TextCondition(DataObject):
    """Represents text criteria in Notion."""

    equals: Optional[str] = None
    does_not_equal: Optional[str] = None
    contains: Optional[str] = None
    does_not_contain: Optional[str] = None
    starts_with: Optional[str] = None
    ends_with: Optional[str] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class NumberCondition(DataObject):
    """Represents number criteria in Notion."""

    equals: Optional[Union[float, int]] = None
    does_not_equal: Optional[Union[float, int]] = None
    greater_than: Optional[Union[float, int]] = None
    less_than: Optional[Union[float, int]] = None
    greater_than_or_equal_to: Optional[Union[float, int]] = None
    less_than_or_equal_to: Optional[Union[float, int]] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class CheckboxCondition(DataObject):
    """Represents checkbox criteria in Notion."""

    equals: Optional[bool] = None
    does_not_equal: Optional[bool] = None


class SelectCondition(DataObject):
    """Represents select criteria in Notion."""

    equals: Optional[str] = None
    does_not_equal: Optional[str] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class MultiSelectCondition(DataObject):
    """Represents a multi_select criteria in Notion."""

    contains: Optional[str] = None
    does_not_contains: Optional[str] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class DateCondition(DataObject):
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


class PeopleCondition(DataObject):
    """Represents people criteria in Notion."""

    contains: Optional[UUID] = None
    does_not_contain: Optional[UUID] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class FilesCondition(DataObject):
    """Represents files criteria in Notion."""

    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class RelationCondition(DataObject):
    """Represents relation criteria in Notion."""

    contains: Optional[UUID] = None
    does_not_contain: Optional[UUID] = None
    is_empty: Optional[bool] = None
    is_not_empty: Optional[bool] = None


class FormulaCondition(DataObject):
    """Represents formula criteria in Notion."""

    string: Optional[TextCondition] = None
    checkbox: Optional[CheckboxCondition] = None
    number: Optional[NumberCondition] = None
    date: Optional[DateCondition] = None


class QueryFilter(DataObject):
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

    @classmethod
    def create(cls, kind, constraint):
        """Create a new `TimeStampFilter` using the given constraint."""

        if kind == TimestampKind.CREATED_TIME:
            return CreatedTimeFilter.create(constraint)

        if kind == TimestampKind.LAST_EDITED_TIME:
            return LastEditedTimeFilter.create(constraint)

        raise ValueError("Unsupported kind for timestamp")


class CreatedTimeFilter(TimestampFilter):
    """Represents a created_time filter in Notion."""

    timestamp: TimestampKind = TimestampKind.CREATED_TIME
    created_time: DateCondition

    @classmethod
    def create(cls, constraint):
        """Create a new `CreatedTimeFilter` using the given constraint."""
        return CreatedTimeFilter(created_time=constraint)


class LastEditedTimeFilter(TimestampFilter):
    """Represents a last_edited_time filter in Notion."""

    timestamp: TimestampKind = TimestampKind.LAST_EDITED_TIME
    last_edited_time: DateCondition

    @classmethod
    def create(cls, constraint):
        """Create a new `LastEditedTimeFilter` using the given constraint."""
        return LastEditedTimeFilter(last_edited_time=constraint)


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


class PropertySort(DataObject):
    """Represents a sort instruction in Notion."""

    property: Optional[str] = None
    timestamp: Optional[TimestampKind] = None
    direction: Optional[SortDirection] = None


class Query(DataObject):
    """Represents a query object in Notion."""

    sorts: Optional[List[PropertySort]] = None
    filter: Optional[QueryFilter] = None
    start_cursor: Optional[UUID] = None
    page_size: int = 100

    @validator("page_size")
    def valid_page_size(cls, value):
        """Validate that the given page size meets the Notion API requirements."""

        assert value > 0, "size must be greater than zero"
        assert value <= 100, "size must be less than or equal to 100"
        return value


class QueryBuilder:
    """A query builder for the Notion API.

    :param endpoint: the session endpoint used to execute the query
    :param cls: an optional DataObject class for parsing results
    :param params: optional params that will be passed to the query
    """

    def __init__(self, endpoint, cls=None, **params):
        """Initialize a new `QueryBuilder` for the given endpoint."""

        self.endpoint = endpoint
        self.params = params
        self.cls = cls

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

    def limit(self, page_size):
        """Limit the number of results to the given page size."""

        self.query.page_size = page_size

        return self

    def execute(self):
        """Execute the current query and return an iterator for the results."""

        if self.endpoint is None:
            raise ValueError("cannot execute query; no endpoint provided")

        _log.debug("executing query - %s", self.query)

        query = self.query.to_api()

        if self.params:
            query.update(self.params)

        exec = EndpointIterator(endpoint=self.endpoint, **query)

        return ResultSet(exec=exec, cls=self.cls)

    def first(self):
        """Execute the current query and return the first result only."""

        try:
            return next(self.execute())
        except StopIteration:
            _log.debug("iterator returned empty result set")

        return None


class ResultSet:
    """A result for a specific query."""

    def __init__(self, exec, cls=None):
        """Initialize a new `ResultSet`."""
        self.source = exec
        self.cls = cls

    def __iter__(self):
        """Return an iterator for this `ResultSet`."""
        return self

    def __next__(self):
        """Return the next item from this `ResultSet`."""

        item = next(self.source)

        if self.cls is not None:
            item = self.cls.parse_obj(item)

        elif "object" in item:
            if item["object"] == "page":
                item = Page.parse_obj(item)
            elif item["object"] == "database":
                item = Database.parse_obj(item)
            elif item["object"] == "block":
                item = Block.parse_obj(item)
            else:
                item = Record.parse_obj(item)

        return item

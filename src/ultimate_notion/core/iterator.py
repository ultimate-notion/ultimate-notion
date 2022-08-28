"""Iterator classes for notional."""

import logging
from abc import ABC, abstractmethod
from typing import Any, List, Optional

from pydantic import BaseModel

CONTENT_PAGE_SIZE = 100

log = logging.getLogger(__name__)


class ContentIterator(ABC):
    """Base class to handle pagination over arbitrary content."""

    def __init__(self):
        """Initialize the iterator."""
        self.log = log.getChild("ContentIterator")

        self.page = None
        self.page_index = -1
        self.page_num = 0
        self.n_items = 0

    def __iter__(self):
        """Initialize the iterator."""
        self.log.debug("initializing content iterator")

        return self

    def __next__(self):
        """Return the next item from the result set or raise StopIteration."""
        # load a new page if needed
        if self.page is None or self.page_index >= len(self.page):
            self.page_index = 0
            self.page = self.load_next_page()
            self.page_num += 1

        # if we have run out of results...
        if self.page is None or len(self.page) == 0:
            raise StopIteration

        # pull the next item from the current page
        item = self.page[self.page_index]

        # setup for the next call
        self.page_index += 1
        self.n_items += 1

        return item

    @property
    def page_number(self):
        """Return the current page number of results in this iterator."""
        return self.page_num

    @property
    def total_items(self):
        """Return the total number of items returns by this iterator."""
        return self.n_items

    @abstractmethod
    def load_next_page(self):
        """Retrieve the next page of data as a list of items."""


class PageIterator(ContentIterator, ABC):
    """Base class to handle pagination by page number."""

    def load_next_page(self):
        """Retrieve the next page of data as a list of items."""
        return self.get_page_content(self.page_num + 1)

    @abstractmethod
    def get_page_content(self, page_num):
        """Retrieve the page of data with the given number."""


class PositionalIterator(ContentIterator, ABC):
    """Base class to handle pagination by positional cursor."""

    def __init__(self):
        """Initialize the iterator."""
        super().__init__()
        self.cursor = None
        self.first_pass = True

    def load_next_page(self):
        """Load the next page of data from this iterator."""

        if not self.first_pass and not self.cursor:
            return None

        results = self.get_page_data(self.cursor)

        self.cursor = results.next_cursor
        self.first_pass = False

        return results.items

    @abstractmethod
    def get_page_data(self, cursor):
        """Retrieve the page of data starting at the given cursor."""

    class PageData(BaseModel):
        """Represents a page of data from the Notion API."""

        this_cursor: Optional[Any] = None
        next_cursor: Optional[Any] = None
        items: Optional[List[Any]] = None

        @property
        def page_size(self):
            """Return the page size for this data set."""
            return -1 if self.items is None else len(self.items)


class ResultSetIterator(PositionalIterator, ABC):
    """Base class for iterating over Notion API result sets."""

    def get_page_data(self, cursor):
        """Retrieve the page of data starting at the given cursor."""

        params = {"page_size": CONTENT_PAGE_SIZE}

        if cursor:
            params["start_cursor"] = cursor

        self.log.debug("loading next page - start cursor: %s", cursor)

        # TODO error checking on result
        data = self.load_page_data(params)

        results = PositionalIterator.PageData(
            this_cursor=cursor,
            next_cursor=data["next_cursor"] if data["has_more"] else None,
            items=data["results"] if "results" in data else None,
        )

        self.log.debug(
            "loaded %d results; next cursor: %s", results.page_size, results.next_cursor
        )

        return results

    @property
    def last_page(self):
        """Return true if this is the last page of results."""
        return not self.first_pass and self.cursor is None

    @abstractmethod
    def load_page_data(self, params):
        """Load the page of data defined by the given params."""


class EndpointIterator(ResultSetIterator):
    """Base class for iterating over results from an API endpoint."""

    def __init__(self, endpoint, **params):
        """Initialize the `EndpointIterator` for a specific API endpoint.

        :param endpoint: the concrete endpoint to use for this iterator
        :param params: parameters sent to the endpoint when called
        """
        super().__init__()

        self.endpoint = endpoint
        self.params = params or {}
        self.log = log.getChild("EndpointIterator")

    def __setitem__(self, name, value):
        """Set the parameter in this `EndpointIterator`."""
        self.params[name] = value

    def load_page_data(self, params):
        """Return the next page with given parameters."""
        params.update(self.params)
        return self.endpoint(**params)

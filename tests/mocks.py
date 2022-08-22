"""Mocks to help with unit testing."""

import math
from random import random
from typing import Any

from pydantic import BaseModel


class MockDataObject(BaseModel):
    """A mock object that mirrors the data returned from `mock_endpoint(...)`."""

    index: int
    pagenum: int
    data: float
    content: Any


# TODO return bad data / errors from endpoint
# TODO support basic filter & sort


def mock_endpoint(item_count, page_size):
    """Simulate a Notion list endpoint by returning pages of data.

    Each "page" in the result set includes one or more items.  Each item on the page
    includes the following fields:

        - index: the item index for the entry, unique in the result set
        - pagenum: the current page number in the result set
        - data: a random number
        - content: optional user content provided to the mock

    :param item_count: the total number of items in the list
    :param page_size: the size of each page of data
    """

    def page_generator(**kwargs):
        """Generate the next page for the mock endpoint using the supplied keywords.

        :param start_cursor: the starting item index for the result set
        :param user_data: optional data that will be provided in the `content`
            field for each item in the result set
        """

        start = int(kwargs.get("start_cursor", 0))
        user_data = kwargs.get("user_data", None)
        pagenum = math.floor(start / page_size) + 1

        page = []

        for x in range(start, start + page_size):
            if x >= item_count:
                continue

            data = {
                "index": x,
                "pagenum": pagenum,
                "content": user_data,
                "data": random(),
            }

            page.append(data)

        return {
            "next_cursor": str(start + page_size),
            "has_more": (start + len(page) < item_count),
            "results": page,
        }

    return page_generator

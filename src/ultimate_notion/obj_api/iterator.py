"""Iterator classes for working with paginated API responses."""

import logging
from typing import Any

from pydantic import Field, validator

from ultimate_notion.obj_api.blocks import Block, Database, Page
from ultimate_notion.obj_api.core import GenericObject, NotionObject, TypedObject
from ultimate_notion.obj_api.objects import User
from ultimate_notion.obj_api.props import PropertyItem

MAX_PAGE_SIZE = 100

logger = logging.getLogger(__name__)


class ObjectList(NotionObject, TypedObject, object='list', polymorphic_base=True):
    """A paginated list of objects returned by the Notion API."""

    results: list[NotionObject] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str | None = None

    # TODO[pydantic]: We couldn't refactor the `validator`, please replace it by `field_validator` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-validators for more information.
    @validator('results', pre=True, each_item=True)
    @classmethod
    def _convert_results_list(cls, val):
        """Convert the results list to specific objects."""

        if 'object' not in val:
            msg = 'Unknown object in results'
            raise ValueError(msg)

        if val['object'] == BlockList.type:
            return Block.model_validate(val)

        if val['object'] == PageList.type:
            return Page.model_validate(val)

        if val['object'] == DatabaseList.type:
            return Database.model_validate(val)

        if val['object'] == PropertyItemList.type:
            return PropertyItem.model_validate(val)

        if val['object'] == UserList.type:
            return User.model_validate(val)

        return GenericObject.model_validate(val)


class BlockList(ObjectList, type='block'):
    """A list of Block objects returned by the Notion API."""

    block: Any = Field(default_factory=dict)


class PageList(ObjectList, type='page'):
    """A list of Page objects returned by the Notion API."""

    page: Any = Field(default_factory=dict)


class DatabaseList(ObjectList, type='database'):
    """A list of Database objects returned by the Notion API."""

    database: Any = Field(default_factory=dict)


class PageOrDatabaseList(ObjectList, type='page_or_database'):
    """A list of Page or Database objects returned by the Notion API."""

    page_or_database: Any = Field(default_factory=dict)


class UserList(ObjectList, type='user'):
    """A list of User objects returned by the Notion API."""

    user: Any = Field(default_factory=dict)


class PropertyItemList(ObjectList, type='property_item'):
    """A paginated list of property items returned by the Notion API.

    Property item lists contain one or more pages of basic property items.  These types
    do not typically match the schema for corresponding property values.
    """

    class _NestedData(GenericObject):
        id: str = None  # noqa: A003
        type: str = None  # noqa: A003
        next_url: str | None = None

    property_item: _NestedData = _NestedData()


class EndpointIterator:
    """Iterates over results from a paginated API response.

    These objects may be reused, however they are not thread safe.  For example,
    after creating the following iterator:

        notion = notional.connect(auth=NOTION_AUTH_TOKEN)
        query = EndpointIterator(notion.databases().query)

    The iterator may be reused with different database ID's:

        for items in query(database_id=first_db):
            ...

        for items in query(database_id=second_db):
            ...

    Objects returned by the iterator may also be converted to a specific type.  This
    is most commonly used to wrap API objects with a higher-level object (such as ORM
    types).
    """

    def __init__(self, endpoint, datatype=None):
        """Initialize an object list iterator for the specified endpoint.

        If a class is provided, it will be constructued for each result returned by
        this iterator.  The constructor must accept a single argument, which is the
        `NotionObject` contained in the `ObjectList`.
        """
        self._endpoint = endpoint
        self._datatype = datatype

        self.has_more = None
        self.page_num = -1
        self.total_items = -1
        self.next_cursor = None

    def __call__(self, **kwargs):
        """Return a generator for this endpoint using the given parameters."""

        self.has_more = True
        self.page_num = 0
        self.total_items = 0

        if 'page_size' not in kwargs:
            kwargs['page_size'] = MAX_PAGE_SIZE

        self.next_cursor = kwargs.pop('start_cursor', None)

        while self.has_more:
            self.page_num += 1

            result_page = self._endpoint(start_cursor=self.next_cursor, **kwargs)

            api_list = ObjectList.model_validate(result_page)

            for obj in api_list.results:
                self.total_items += 1

                if self._datatype is None:
                    yield obj
                else:
                    yield self._datatype(obj)

            self.next_cursor = api_list.next_cursor
            self.has_more = api_list.has_more and self.next_cursor is not None

    def as_list(self, **kwargs):
        """Collect all items from the endpoint as a list."""

        items = []

        for item in self(**kwargs):
            items.append(item)

        return items

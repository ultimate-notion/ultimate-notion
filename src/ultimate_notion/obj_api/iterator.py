"""Iterator classes for working with paginated API responses."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterator
from typing import Annotated, Any

from pydantic import ConfigDict, Field
from pydantic.functional_validators import BeforeValidator

from ultimate_notion.obj_api.blocks import Block, Database, Page
from ultimate_notion.obj_api.core import GenericObject, NotionObject, TypedObject
from ultimate_notion.obj_api.objects import Comment, User
from ultimate_notion.obj_api.props import PropertyItem

MAX_PAGE_SIZE = 100

logger = logging.getLogger(__name__)


def convert_to_notion_obj(data: dict[str, Any]) -> Block | Page | Database | PropertyItem | User | GenericObject:
    """Convert a dictionary to the corresponding subtype of Notion Object.

    Used in the ObjectList below the convert the results from the Notion API.
    """
    obj_field = 'object'

    if obj_field not in data:
        msg = 'Unknown object in results'
        raise ValueError(msg)

    models: tuple[type[NotionObject], ...] = (Block, Page, Database, PropertyItem, User, Comment)
    model_mapping = {model.model_fields[obj_field].default: model for model in models}
    model_class = model_mapping.get(data[obj_field], GenericObject)
    return model_class.model_validate(data)


class ObjectList(NotionObject, TypedObject, object='list', polymorphic_base=True):
    """A paginated list of objects returned by the Notion API.

    More details in the [Notion API](https://developers.notion.com/reference/intro#responses).
    """

    results: list[Annotated[NotionObject, BeforeValidator(convert_to_notion_obj)]] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str | None = None


class BlockList(ObjectList, type='block'):
    """A list of Block objects returned by the Notion API."""

    class TypeData(GenericObject): ...

    block: TypeData


class PageOrDatabaseList(ObjectList, type='page_or_database'):
    """A list of Page or Database objects returned by the Notion API."""

    class TypeData(GenericObject): ...

    page_or_database: TypeData


class UserList(ObjectList, type='user'):
    """A list of User objects returned by the Notion API."""

    class TypeData(GenericObject): ...

    user: TypeData


class CommentList(ObjectList, type='comment'):
    """A list of Comment objects returned by the Notion API."""

    class TypeData(GenericObject): ...

    comment: TypeData


class PropertyItemList(ObjectList, type='property_item'):
    """A paginated list of property items returned by the Notion API.

    Property item lists contain one or more pages of basic property items.  These types
    do not typically match the schema for corresponding property values.
    """

    class TypeData(GenericObject):
        model_config = ConfigDict(extra='allow')  # for additional `type` field
        id: str
        type: str
        next_url: str | None  # not clear what this is for

    property_item: TypeData


class EndpointIterator:
    """Functor to iterate over results from a paginated API response."""

    has_more: bool | None = None
    page_num: int = -1
    total_items: int = -1
    next_cursor: str | None = None

    def __init__(self, endpoint: Callable[..., Any | Awaitable[Any]]):
        """Initialize an object list iterator for the specified endpoint."""
        self._endpoint = endpoint

    def __call__(self, **kwargs: Any) -> Iterator[NotionObject]:
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

            obj_list = ObjectList.model_validate(result_page)

            for obj in obj_list.results:
                self.total_items += 1
                yield obj

            self.next_cursor = obj_list.next_cursor
            self.has_more = obj_list.has_more and self.next_cursor is not None

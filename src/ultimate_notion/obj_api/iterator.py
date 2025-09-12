"""Iterator classes for working with paginated API responses."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterator
from typing import Annotated, Any, Generic, TypeVar, cast

from pydantic import ConfigDict, Field
from pydantic.functional_validators import BeforeValidator

from ultimate_notion.obj_api.blocks import Block, Database, Page
from ultimate_notion.obj_api.core import GenericObject, NotionObject, TypedObject
from ultimate_notion.obj_api.objects import Comment, FileUpload, User
from ultimate_notion.obj_api.props import PropertyItem

MAX_PAGE_SIZE = 100

_logger = logging.getLogger(__name__)


def convert_to_notion_obj(
    data: dict[str, Any],
) -> Block | Page | Database | PropertyItem | User | GenericObject | FileUpload:
    """Convert a dictionary to the corresponding subtype of Notion Object.

    Used in the ObjectList below the convert the results from the Notion API.
    """
    obj_field = 'object'

    if obj_field not in data:
        msg = 'Unknown object in results'
        raise ValueError(msg)

    models: tuple[type[NotionObject], ...] = (Block, Page, Database, PropertyItem, User, Comment, FileUpload)
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


class FileUploadList(ObjectList, type='file_upload'):
    """A list of FileUpload objects returned by the Notion API."""

    class TypeData(GenericObject): ...

    file_upload: TypeData


T = TypeVar('T', bound=NotionObject)


class EndpointIterator(Generic[T]):
    """Functor to iterate over results from a potentially paginated API response.

    In most cases `notion_obj` should be `ObjectList`. For some endpoints, like `PropertiesEndpoint`, and
    endpoint returns a list of property items or s single property item. In this case, `model_validate` should be
    `TypeAdapter(PropertyItemList | PropertyItem).validate_python` or whatever you expect to be returned.
    """

    has_more: bool | None = None
    page_num: int = -1
    total_items: int = -1
    next_cursor: str | None = None

    def __init__(
        self,
        endpoint: Callable[..., Any | Awaitable[Any]],
        *,
        pagination: Callable[..., Any | Awaitable[Any]] | None = None,
        model_validate: Callable[[Any], NotionObject] = ObjectList.model_validate,
    ):
        """Initialize an object list iterator for the specified endpoint."""
        self._endpoint = endpoint
        self._pagination = pagination
        self._model_validate = model_validate

    def __call__(self, **kwargs: Any) -> Iterator[T]:
        """Return a generator for this endpoint using the given parameters."""

        self.has_more = True
        self.page_num = 0
        self.total_items = 0

        if 'page_size' not in kwargs:
            kwargs['page_size'] = MAX_PAGE_SIZE

        self.next_cursor = kwargs.pop('start_cursor', None)

        while self.has_more:
            self.page_num += 1

            if self.next_cursor is None:
                msg = f'Fetching last page {self.page_num} of endpoint.'
            else:
                msg = f'Fetching page {self.page_num} of endpoint with next cursor {self.next_cursor}.'
            _logger.debug(msg)

            result_page = self._endpoint(start_cursor=self.next_cursor, **kwargs)
            obj_or_list = self._model_validate(result_page)

            if isinstance(obj_or_list, ObjectList):
                for obj in obj_or_list.results:
                    self.total_items += 1
                    yield cast(T, obj)

                self.next_cursor = obj_or_list.next_cursor
                self.has_more = obj_or_list.has_more and self.next_cursor is not None
                if self.has_more and self._pagination is not None:
                    # Some endpoints like `blocks.children.append` use a different endpoint for pagination.
                    # If not used, the action, e.g. appending blocks, will be repeated.
                    # You gotta love the Notion API...
                    self._endpoint = self._pagination
            else:
                yield cast(T, obj_or_list)
                self.has_more = False

            _logger.debug(f'Fetched {self.total_items} item(s) in total over {self.page_num} page(s).')

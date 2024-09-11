"""Provides an object-based Notion API with all endpoints.

This pydantic based API is often referred to as just `api` while the low-level
API of the [Notion Client SDK library](https://github.com/ramnes/notion-sdk-py)
is just referred to as `raw_api`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, cast
from uuid import UUID

from pydantic import SerializeAsAny, TypeAdapter

from ultimate_notion.obj_api.blocks import Block, Database, FileBase, Page
from ultimate_notion.obj_api.iterator import EndpointIterator, PropertyItemList
from ultimate_notion.obj_api.objects import (
    DatabaseRef,
    EmojiObject,
    FileObject,
    GenericObject,
    ObjectReference,
    PageRef,
    ParentRef,
    RichTextBaseObject,
    User,
)
from ultimate_notion.obj_api.props import PropertyItem, Title
from ultimate_notion.obj_api.query import DBQueryBuilder, SearchQueryBuilder
from ultimate_notion.obj_api.schema import PropertyType

if TYPE_CHECKING:
    from notion_client import Client as NCClient
    from notion_client.api_endpoints import BlocksChildrenEndpoint as NCBlocksChildrenEndpoint
    from notion_client.api_endpoints import BlocksEndpoint as NCBlocksEndpoint
    from notion_client.api_endpoints import DatabasesEndpoint as NCDatabasesEndpoint

logger = logging.getLogger(__name__)
T_UNSET: TypeAlias = Literal['UNSET']
UNSET: T_UNSET = 'UNSET'


class SessionError(Exception):
    """Raised when there are issues with the Notion session."""

    def __init__(self, message):
        """Initialize the `SessionError` with a supplied message."""
        super().__init__(message)


class NotionAPI:
    """Object-based Notion API (pydantic) with all endpoints."""

    def __init__(self, client: NCClient):
        self.client = client

        self.blocks = BlocksEndpoint(self)
        self.databases = DatabasesEndpoint(self)
        self.pages = PagesEndpoint(self)
        self.search = SearchEndpoint(self)
        self.users = UsersEndpoint(self)


class Endpoint:
    """Baseclass of the Notion API endpoints."""

    def __init__(self, api: NotionAPI):
        self.api = api


class BlocksEndpoint(Endpoint):
    """Interface to the 'blocks' endpoint of the Notion API"""

    class ChildrenEndpoint(Endpoint):
        """Interface to the API 'blocks/children' endpoint."""

        @property
        def raw_api(self) -> NCBlocksChildrenEndpoint:
            """Return the underlying endpoint in the Notion SDK."""
            return self.api.client.blocks.children

        # https://developers.notion.com/reference/patch-block-children
        def append(
            self, parent: ParentRef | GenericObject | UUID | str, blocks: list[Block], *, after: Block | None = None
        ) -> tuple[list[Block], list[Block]]:
            """Add the given blocks as children of the specified parent.

            The blocks info of the passed blocks will be updated and returned as first part of a tuple.
            The second party of the tuple is an empty list or the updated blocks after the specified block
            if `after` was specified. Use this to update the blocks with the latest version from the server.
            """

            parent_id = ObjectReference.build(parent).id
            children = [block.serialize_for_api() for block in blocks if block is not None]

            logger.info('Appending %d blocks to %s ...', len(children), parent_id)

            endpoint_iter = EndpointIterator(endpoint=self.raw_api.append)
            if after is None:
                appended_blocks = list(endpoint_iter(block_id=parent_id, children=children))
                if len(appended_blocks) != len(blocks):
                    msg = 'Number of appended blocks does not match the number of provided blocks.'
                    raise ValueError(msg)
            else:
                appended_blocks = list(endpoint_iter(block_id=parent_id, children=children, after=str(after.id)))

            # the first len(blocks) of appended_blocks correspond to the blocks we passed, the rest are updated
            # blocks after the specified block, where we append the blocks.
            for block, appended_block in zip(blocks, appended_blocks[: len(blocks)], strict=True):
                block.update(**appended_block.serialize_for_api())

            return blocks, cast(list[Block], appended_blocks[len(blocks) :])

        # https://developers.notion.com/reference/get-block-children
        def list(self, parent: ParentRef | GenericObject | UUID | str) -> Iterator[Block]:
            """Return all Blocks contained by the specified parent.

            `parent` may be any suitable `ObjectReference` type.
            """

            parent_id = ObjectReference.build(parent).id

            logger.info('Listing blocks for %s...', parent_id)

            blocks = EndpointIterator(endpoint=self.raw_api.list)

            return cast(Iterator[Block], blocks(block_id=parent_id))

    def __init__(self, *args, **kwargs):
        """Initialize the `blocks` endpoint for the Notion API."""
        super().__init__(*args, **kwargs)

        self.children = BlocksEndpoint.ChildrenEndpoint(*args, **kwargs)

    @property
    def raw_api(self) -> NCBlocksEndpoint:
        """Return the underlying endpoint in the Notion SDK."""
        return self.api.client.blocks

    # https://developers.notion.com/reference/delete-a-block
    def delete(self, block: Block | UUID | str) -> Block:
        """Delete (archive) the specified Block.

        `block` may be any suitable `ObjectReference` type.
        """

        block_id = str(ObjectReference.build(block).id)
        logger.info('Deleting block :: %s', block_id)

        data = self.raw_api.delete(block_id)

        return Block.model_validate(data)

    def restore(self, block: Block | UUID | str) -> Block:
        """Restore (unarchive) the specified Block.

        `block` may be any suitable `ObjectReference` type.
        """

        block_id = str(ObjectReference.build(block).id)
        logger.info('Restoring block :: %s', block_id)

        data = self.raw_api.update(block_id, archived=False)

        return Block.model_validate(data)

    # https://developers.notion.com/reference/retrieve-a-block
    def retrieve(self, block: Block | UUID | str) -> Block:
        """Return the requested Block.

        `block` may be any suitable `ObjectReference` type.
        """

        block_id = str(ObjectReference.build(block).id)
        logger.info('Retrieving block :: %s', block_id)

        data = self.raw_api.retrieve(block_id)

        return Block.model_validate(data)

    # https://developers.notion.com/reference/update-a-block
    def update(self, block: Block) -> Block:
        """Update the block content on the server.

        The block info will be updated to the latest version from the server.
        """

        logger.info('Updating block :: %s', block.id)

        params = block.serialize_for_api()
        if isinstance(block, FileBase):
            # The Notiopn API does not support setting a new typed FileObject, e.g. `external` or `file`
            # It even must be removed from the params
            dtype = params[block.type].pop('type')
            del params[block.type][dtype]
        # Typing in notion_client sucks, so we cast
        data = cast(dict[str, Any], self.raw_api.update(block.id.hex, **params))

        return block.update(**data)


class DatabasesEndpoint(Endpoint):
    """Interface to the 'databases' endpoint of the Notion API."""

    @property
    def raw_api(self) -> NCDatabasesEndpoint:
        """Return the underlying endpoint in the Notion SDK."""
        return self.api.client.databases

    @staticmethod
    def _build_request(
        parent: SerializeAsAny[ParentRef] | None = None,
        schema: dict[str, PropertyType] | None = None,
        title: list[RichTextBaseObject] | None = None,
        description: list[RichTextBaseObject] | None = None,
    ) -> dict[str, Any]:
        """Build a request payload from the given items.

        *NOTE* this method does not anticipate what the request will be used for and as
        such does not validate the inputs for any particular requests.
        """
        request: dict[str, Any] = {}

        if parent is not None:
            request['parent'] = parent.serialize_for_api()

        if title is not None:
            request['title'] = [rt_obj.serialize_for_api() for rt_obj in title]

        if description is not None:
            request['description'] = [rt_obj.serialize_for_api() for rt_obj in description]

        if schema is not None:
            request['properties'] = {
                name: value.serialize_for_api() if value is not None else None for name, value in schema.items()
            }

        return request

    # https://developers.notion.com/reference/create-a-database
    def create(
        self, parent: Page, schema: dict[str, PropertyType], title: list[RichTextBaseObject] | None = None
    ) -> Database:
        """Add a database to the given Page parent.

        `parent` may be any suitable `PageRef` type.
        """

        parent_ref = PageRef.build(parent)
        logger.info(f'Creating database `{title!s}` at `{parent_ref.page_id}`')

        request = self._build_request(parent_ref, schema, title)
        data = self.raw_api.create(**request)

        return Database.model_validate(data)

    # https://developers.notion.com/reference/retrieve-a-database
    def retrieve(self, dbref: Database | str | UUID) -> Database:
        """Return the Database with the given ID.

        `dbref` may be any suitable `DatabaseRef` type.
        """

        db_id = DatabaseRef.build(dbref).database_id
        logger.info(f'Retrieving database with id `{db_id}`')
        data = self.raw_api.retrieve(str(db_id))

        return Database.model_validate(data)

    def update(
        self,
        db: Database,
        title: list[RichTextBaseObject] | None = None,
        description: list[RichTextBaseObject] | None = None,
        schema: dict[str, PropertyType] | None = None,
    ) -> Database:
        """Update the Database object on the server.

        The database info will be updated to the latest version from the server.

        API reference: https://developers.notion.com/reference/update-a-database
        """
        logger.info(f'Updating database info of `{db.title}`')

        if request := self._build_request(schema=schema, title=title, description=description):
            # https://github.com/ramnes/notion-sdk-py/blob/main/notion_client/api_endpoints.py
            # Typing in notion_client sucks, thus we cast
            data = cast(dict[str, Any], self.raw_api.update(str(db.id), **request))
            db = db.update(**data)

        return db

    def delete(self, db: Database) -> Database:
        """Delete (archive) the specified Database."""

        db_id = DatabaseRef.build(db).database_id

        logger.info(f'Deleting database `{db}` with id {db_id}')

        block_obj = self.api.blocks.delete(str(db_id))
        # block.update(**data) is not possible as the API returns a block, not a database
        db.archived = block_obj.archived  # ToDo: Remove when `archived` is completely deprecated
        db.in_trash = block_obj.in_trash
        return db

    def restore(self, db: Database) -> Database:
        """Restore (unarchive) the specified Database."""

        db_id = DatabaseRef.build(db).database_id

        logger.info(f'Restoring database `{db}` with id {db_id}')

        block_obj = self.api.blocks.restore(str(db_id))
        # block.update(**data) is not possible as the API returns a block, not a database
        db.archived = block_obj.archived  # ToDo: Remove when `archived` is completely deprecated
        db.in_trash = block_obj.in_trash
        return db

    # https://developers.notion.com/reference/post-database-query
    def query(self, db: Database | UUID | str) -> DBQueryBuilder:
        """Initialize a new Query object with the target data class."""
        db_id = DatabaseRef.build(db).database_id
        logger.info('Initializing database query :: {%s}', db_id)

        return DBQueryBuilder(endpoint=self.raw_api.query, db_id=str(db_id))


class PagesEndpoint(Endpoint):
    """Interface to the API 'pages' endpoint."""

    class PropertiesEndpoint(Endpoint):
        """Interface to the API 'pages/properties' endpoint."""

        @property
        def raw_api(self):
            """Return the underlying endpoint in the Notion SDK"""
            return self.api.client.pages.properties

        # https://developers.notion.com/reference/retrieve-a-page-property
        def retrieve(self, page_id, property_id):
            """Return the Property on a specific Page with the given ID"""

            logger.info('Retrieving property :: %s [%s]', property_id, page_id)

            data = self.raw_api.retrieve(page_id, property_id)

            # TODO should PropertyListItem return an iterator instead?
            return TypeAdapter(PropertyItem | PropertyItemList).validate_python(data)

    def __init__(self, *args, **kwargs):
        """Initialize the `pages` endpoint for the Notion API"""
        super().__init__(*args, **kwargs)

        self.properties = PagesEndpoint.PropertiesEndpoint(*args, **kwargs)

    @property
    def raw_api(self):
        """Return the underlying endpoint in the Notion SDK"""
        return self.api.client.pages

    # https://developers.notion.com/reference/post-page
    def create(self, parent, title: Title | None = None, properties=None, children=None) -> Page:
        """Add a page to the given parent (Page or Database).

        `parent` may be a `ParentRef`, `Page`, or `Database` object.
        """

        if parent is None:
            msg = "'parent' must be provided"
            raise ValueError(msg)

        if isinstance(parent, Page):
            parent = PageRef.build(parent)
        elif isinstance(parent, Database):
            parent = DatabaseRef.build(parent)
        elif not isinstance(parent, ParentRef):
            msg = "Unsupported 'parent'"
            raise ValueError(msg)

        request = {'parent': parent.serialize_for_api()}

        # the API requires a properties object, even if empty
        if properties is None:
            properties = {}

        if title is not None:
            properties['title'] = title

        request['properties'] = {
            name: prop.serialize_for_api() if prop is not None else None for name, prop in properties.items()
        }

        if children is not None:
            request['children'] = [child.serialize_for_api() for child in children if child is not None]

        logger.info('Creating page :: %s => %s', parent, title)

        data = self.raw_api.create(**request)

        return Page.model_validate(data)

    def delete(self, page: Page) -> Page:
        """Delete (archive) the specified Page.

        `page` may be any suitable `PageRef` type.
        """

        return self.set_attr(page, in_trash=True)

    def restore(self, page: Page) -> Page:
        """Restore (unarchive) the specified Page.

        `page` may be any suitable `PageRef` type.
        """

        return self.set_attr(page, in_trash=False)

    # https://developers.notion.com/reference/retrieve-a-page
    def retrieve(self, page: Page | UUID | str) -> Page:
        """Return the requested Page.

        `page` may be any suitable `PageRef` type.
        """

        page_id = PageRef.build(page).page_id

        logger.info('Retrieving page :: %s', page_id)

        data = self.raw_api.retrieve(page_id)

        # ToDo: would it make sense to (optionally) expand the full properties here?
        # e.g. call the PropertiesEndpoint to make sure all data is retrieved

        return Page.model_validate(data)

    # https://developers.notion.com/reference/patch-page
    def update(self, page: Page, **properties) -> Page:
        """Update the Page object properties on the server.

        An optional `properties` may be specified as `"name"`: `PropertyValue` pairs.

        If `properties` are provided, only those values will be updated.
        If `properties` is empty, all page properties will be updated.

        The page info will be updated to the latest version from the server.
        """

        logger.info('Updating page info :: %s', page.id)

        if not properties:
            properties = page.properties

        props = {name: value.serialize_for_api() if value is not None else None for name, value in properties.items()}
        data = self.raw_api.update(page.id.hex, properties=props)

        return page.update(**data)

    def set_attr(
        self,
        page: Page,
        *,
        cover: FileObject | None | T_UNSET = UNSET,
        icon: FileObject | EmojiObject | None | T_UNSET = UNSET,
        in_trash: bool | T_UNSET = UNSET,
    ) -> Page:
        """Set specific page attributes (such as cover, icon, etc.) on the server.

        `page` may be any suitable `PageRef` type.

        To remove an attribute, set its value to None.
        """

        page_id = PageRef.build(page).page_id

        props: dict[str, Any] = {}

        if cover is not UNSET:
            if cover is None:
                logger.info('Removing page cover :: %s', page_id)
                props['cover'] = None
            else:
                logger.info('Setting page cover :: %s => %s', page_id, cover)
                props['cover'] = cover.serialize_for_api()  # type: ignore[union-attr]

        if icon is not UNSET:
            if icon is None:
                logger.info('Removing page icon :: %s', page_id)
                props['icon'] = None
            else:
                logger.info('Setting page icon :: %s => %s', page_id, icon)
                props['icon'] = icon.serialize_for_api()  # type: ignore[union-attr]

        if in_trash is not UNSET:
            if in_trash:
                logger.info('Deleting page :: %s', page_id)
                props['archived'] = True
            else:
                logger.info('Restoring page :: %s', page_id)
                props['archived'] = False

        data = self.raw_api.update(page_id.hex, **props)

        return page.update(**data)


class SearchEndpoint(Endpoint):
    """Interface to the API 'search' endpoint."""

    # https://developers.notion.com/reference/post-search
    def __call__(self, text=None) -> SearchQueryBuilder:
        """Perform a search with the optional text"""
        return SearchQueryBuilder(endpoint=self.api.client.search, text=text)


class UsersEndpoint(Endpoint):
    """Interface to the API 'users' endpoint."""

    @property
    def raw_api(self):
        """Return the underlying endpoint in the Notion SDK"""
        return self.api.client.users

    # https://developers.notion.com/reference/get-users
    def list(self) -> Iterator[User]:
        """Return an iterator for all users in the workspace."""

        logger.info('Listing known users...')

        users = EndpointIterator(endpoint=self.raw_api.list)

        return cast(Iterator[User], users())

    # https://developers.notion.com/reference/get-user
    def retrieve(self, user_id) -> User:
        """Return the User with the given ID."""

        logger.info('Retrieving user :: %s', user_id)

        data = self.raw_api.retrieve(user_id)

        return User.model_validate(data)

    # https://developers.notion.com/reference/get-self
    def me(self) -> User:
        """Return the current bot User."""

        logger.info('Retrieving current integration bot')

        data = self.raw_api.me()

        return User.model_validate(data)

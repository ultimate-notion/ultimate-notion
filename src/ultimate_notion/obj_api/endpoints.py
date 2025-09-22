"""Provides an object-based Notion API with all endpoints.

This pydantic based API is often referred to as `api` while the low-level
API of the [Notion Client SDK library](https://github.com/ramnes/notion-sdk-py)
is referred to as `raw_api`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, BinaryIO, cast
from uuid import UUID

from pydantic import SerializeAsAny, TypeAdapter

from ultimate_notion.obj_api.blocks import Block, Database, FileBase, Page
from ultimate_notion.obj_api.core import Unset, UnsetType, raise_unset
from ultimate_notion.obj_api.enums import FileUploadMode, FileUploadStatus
from ultimate_notion.obj_api.iterator import EndpointIterator, PropertyItemList
from ultimate_notion.obj_api.objects import (
    Bot,
    Comment,
    CustomEmojiObject,
    DatabaseRef,
    EmojiObject,
    FileObject,
    FileUpload,
    GenericObject,
    ObjectRef,
    PageRef,
    ParentRef,
    RichTextBaseObject,
    User,
    UserRef,
)
from ultimate_notion.obj_api.props import PropertyItem, PropertyValue, Title
from ultimate_notion.obj_api.query import DBQueryBuilder, SearchQueryBuilder
from ultimate_notion.obj_api.schema import Property, RenameProp

if TYPE_CHECKING:
    from notion_client import Client as NCClient
    from notion_client.api_endpoints import BlocksChildrenEndpoint as NCBlocksChildrenEndpoint
    from notion_client.api_endpoints import BlocksEndpoint as NCBlocksEndpoint
    from notion_client.api_endpoints import CommentsEndpoint as NCCommentsEndpoint
    from notion_client.api_endpoints import DatabasesEndpoint as NCDatabasesEndpoint
    from notion_client.api_endpoints import FileUploadsEndpoint as NCFileUploadsEndpoint
    from notion_client.api_endpoints import PagesEndpoint as NCPagesEndpoint
    from notion_client.api_endpoints import PagesPropertiesEndpoint as NCPagesPropertiesEndpoint
    from notion_client.api_endpoints import UsersEndpoint as NCUsersEndpoint

_logger = logging.getLogger(__name__)


class NotionAPI:
    """Object-based Notion API (pydantic) with all endpoints."""

    def __init__(self, client: NCClient):
        self.client = client
        self.blocks = BlocksEndpoint(self)
        self.databases = DatabasesEndpoint(self)
        self.pages = PagesEndpoint(self)
        self.search = SearchEndpoint(self)
        self.users = UsersEndpoint(self)
        self.comments = CommentsEndpoint(self)
        self.uploads = UploadsEndpoint(self)


@dataclass
class Endpoint:
    """Baseclass of the Notion API endpoints."""

    api: NotionAPI


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
            parent_id = ObjectRef.build(parent).id
            children = [block.serialize_for_api() for block in blocks if block is not None]
            _logger.debug(f'Appending {len(children)} blocks to parent with id `{parent_id}`.')

            block_iter = EndpointIterator[Block](endpoint=self.raw_api.append, pagination=self.raw_api.list)
            if after is None:
                appended_blocks = list(block_iter(block_id=parent_id, children=children))
                if len(appended_blocks) != len(blocks):
                    msg = 'Number of appended blocks does not match the number of provided blocks.'
                    raise ValueError(msg)
            else:
                appended_blocks = list(
                    block_iter(block_id=parent_id, children=children, after=str(raise_unset(after.id)))
                )

            # the first len(blocks) of appended_blocks correspond to the blocks we passed, the rest are updated
            # blocks after the specified block, where we append the blocks.
            for block, appended_block in zip(blocks, appended_blocks[: len(blocks)], strict=True):
                block.update(**appended_block.serialize_for_api())

            return blocks, appended_blocks[len(blocks) :]

        # https://developers.notion.com/reference/get-block-children
        def list(self, parent: ParentRef | GenericObject | UUID | str) -> Iterator[Block]:
            """Return all Blocks contained by the specified parent."""
            parent_id = ObjectRef.build(parent).id
            _logger.debug(f'Listing all blocks for parent with id `{parent_id}`.')
            block_iter = EndpointIterator[Block](endpoint=self.raw_api.list)
            return block_iter(block_id=parent_id)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the `blocks` endpoint for the Notion API."""
        super().__init__(*args, **kwargs)
        self.children = BlocksEndpoint.ChildrenEndpoint(*args, **kwargs)

    @property
    def raw_api(self) -> NCBlocksEndpoint:
        """Return the underlying endpoint in the Notion SDK."""
        return self.api.client.blocks

    # https://developers.notion.com/reference/delete-a-block
    def delete(self, block: Block | UUID | str) -> Block:
        """Delete (archive) the specified Block."""
        block_id = str(ObjectRef.build(block).id)
        _logger.debug(f'Deleting block with id `{block_id}`.')
        data = self.raw_api.delete(block_id)
        return Block.model_validate(data)

    def restore(self, block: Block | UUID | str) -> Block:
        """Restore (unarchive) the specified Block."""
        block_id = str(ObjectRef.build(block).id)
        _logger.debug(f'Restoring block with id `{block_id}`.')
        data = self.raw_api.update(block_id, archived=False)
        return Block.model_validate(data)

    # https://developers.notion.com/reference/retrieve-a-block
    def retrieve(self, block: Block | UUID | str) -> Block:
        """Return the requested Block."""
        block_id = str(ObjectRef.build(block).id)
        _logger.debug(f'Retrieving block with id `{block_id}`.')
        data = self.raw_api.retrieve(block_id)
        return Block.model_validate(data)

    # https://developers.notion.com/reference/update-a-block
    def update(self, block: Block) -> None:
        """Update the block object on the server.

        The block info will be updated to the latest version from the server.
        """
        block_id = cast(UUID, raise_unset(block.id))  # don't get why mypy needs this cast
        _logger.debug(f'Updating block with id `{block_id}`.')
        params = block.serialize_for_api()

        if isinstance(block, FileBase):
            # The Notiopn API does not support setting a new typed FileObject, e.g. `external` or `file`
            # It even must be removed from the params
            dtype = params[block.type].pop('type')
            del params[block.type][dtype]

        # Typing in notion_client sucks, so we cast
        data = cast(dict[str, Any], self.raw_api.update(block_id.hex, **params))
        block.update(**data)


class DatabasesEndpoint(Endpoint):
    """Interface to the 'databases' endpoint of the Notion API."""

    @property
    def raw_api(self) -> NCDatabasesEndpoint:
        """Return the underlying endpoint in the Notion SDK."""
        return self.api.client.databases

    @staticmethod
    def _build_request(
        *,
        parent: SerializeAsAny[ParentRef] | None = None,
        schema: Mapping[str, Property | RenameProp | None] | None = None,
        title: list[RichTextBaseObject] | None = None,
        description: list[RichTextBaseObject] | None = None,
        inline: bool | None = None,
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

        if inline is not None:
            request['is_inline'] = inline

        return request

    # https://developers.notion.com/reference/create-a-database
    def create(
        self,
        parent: Page,
        schema: Mapping[str, Property],
        *,
        title: list[RichTextBaseObject] | None = None,
        inline: bool = False,
    ) -> Database:
        """Add a database to the given Page parent."""
        parent_ref = PageRef.build(parent)
        _logger.debug(f'Creating new database below page with id `{parent_ref.page_id}`.')
        request = self._build_request(parent=parent_ref, schema=schema, title=title, inline=inline)
        data = self.raw_api.create(**request)
        return Database.model_validate(data)

    # https://developers.notion.com/reference/retrieve-a-database
    def retrieve(self, dbref: Database | str | UUID) -> Database:
        """Return the Database with the given ID."""
        db_id = DatabaseRef.build(dbref).database_id
        _logger.debug(f'Retrieving database with id `{db_id}`.')
        data = self.raw_api.retrieve(str(db_id))
        return Database.model_validate(data)

    def update(
        self,
        db: Database,
        *,
        title: list[RichTextBaseObject] | None = None,
        description: list[RichTextBaseObject] | None = None,
        inline: bool | None = None,
        schema: Mapping[str, Property | RenameProp | None] | None = None,
    ) -> None:
        """Update the Database object on the server.

        The database info will be updated to the latest version from the server.

        API reference: https://developers.notion.com/reference/update-a-database
        """
        _logger.debug(f'Updating info of database with id `{db.id}`.')

        if request := self._build_request(schema=schema, title=title, description=description, inline=inline):
            # https://github.com/ramnes/notion-sdk-py/blob/main/notion_client/api_endpoints.py
            # Typing in notion_client sucks, thus we cast
            data = cast(dict[str, Any], self.raw_api.update(str(db.id), **request))
            db.update(**data)

    def delete(self, db: Database) -> Database:
        """Delete (archive) the specified Database."""
        db_id = DatabaseRef.build(db).database_id
        _logger.debug(f'Deleting database with id `{db_id}`.')
        block_obj = self.api.blocks.delete(str(db_id))
        # block.update(**data) is not possible as the API returns a block, not a database
        db.archived = block_obj.archived  # ToDo: Remove when `archived` is completely deprecated
        db.in_trash = block_obj.in_trash
        return db

    def restore(self, db: Database) -> Database:
        """Restore (unarchive) the specified Database."""
        db_id = DatabaseRef.build(db).database_id
        _logger.debug(f'Restoring database with id `{db_id}`.')
        block_obj = self.api.blocks.restore(str(db_id))
        # block.update(**data) is not possible as the API returns a block, not a database
        db.archived = block_obj.archived  # ToDo: Remove when `archived` is completely deprecated
        db.in_trash = block_obj.in_trash
        return db

    # https://developers.notion.com/reference/post-database-query
    def query(self, db: Database | UUID | str) -> DBQueryBuilder:
        """Initialize a new Query object with the target data class."""
        db_id = DatabaseRef.build(db).database_id
        _logger.debug(f'Initializing query for db with id `{db_id}`.')
        return DBQueryBuilder(endpoint=self.raw_api.query, db_id=str(db_id))


class PagesEndpoint(Endpoint):
    """Interface to the API 'pages' endpoint."""

    class PropertiesEndpoint(Endpoint):
        """Interface to the API 'pages/properties' endpoint."""

        @property
        def raw_api(self) -> NCPagesPropertiesEndpoint:
            """Return the underlying endpoint in the Notion SDK"""
            return self.api.client.pages.properties

        # https://developers.notion.com/reference/retrieve-a-page-property
        def retrieve(self, page: Page | UUID | str, property: PropertyValue | str) -> Iterator[PropertyItem]:  # noqa: A002
            """Return the Property on a specific Page with the given ID"""
            page_id = str(PageRef.build(page).page_id)
            property_id = property.id if isinstance(property, PropertyValue) else property
            _logger.debug(f'Retrieving property with id `{property_id}` from page with id `{page_id}`.')
            prop_iter = EndpointIterator[PropertyItem](
                endpoint=self.raw_api.retrieve,
                model_validate=TypeAdapter(PropertyItemList | PropertyItem).validate_python,
            )
            return prop_iter(page_id=page_id, property_id=property_id)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the `pages` endpoint for the Notion API"""
        super().__init__(*args, **kwargs)
        self.properties = PagesEndpoint.PropertiesEndpoint(*args, **kwargs)

    @property
    def raw_api(self) -> NCPagesEndpoint:
        """Return the underlying endpoint in the Notion SDK"""
        return self.api.client.pages

    # https://developers.notion.com/reference/post-page
    def create(
        self,
        parent: ParentRef | Page | Database,
        title: Title | None = None,
        properties: dict[str, PropertyValue] | None = None,
        children: list[Block] | None = None,
    ) -> Page:
        """Add a page to the given parent (Page or Database)."""
        if parent is None:
            msg = "'parent' must be provided"
            raise ValueError(msg)

        match parent:
            case Page():
                parent = PageRef.build(parent)
                parent_id = parent.page_id
            case Database():
                parent = DatabaseRef.build(parent)
                parent_id = parent.database_id
            case _:
                msg = f'Unsupported parent of type {type(parent)}'
                raise ValueError(msg)

        request: dict[str, Any] = {'parent': parent.serialize_for_api()}

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

        _logger.debug(f'Creating new page below page with id `{parent_id}`.')
        data = self.raw_api.create(**request)
        return Page.model_validate(data)

    def delete(self, page: Page) -> None:
        """Delete (archive) the specified Page."""
        self.set_attr(page, in_trash=True)

    def restore(self, page: Page) -> None:
        """Restore (unarchive) the specified Page."""
        self.set_attr(page, in_trash=False)

    # https://developers.notion.com/reference/retrieve-a-page
    def retrieve(self, page: Page | UUID | str) -> Page:
        """Return the requested Page.

        !!! warning

            This method will only retrieve up to 25 items per property.
            Use `pages.properties.retrieve` to retrieve all items of a specific property.
        """
        page_id = str(PageRef.build(page).page_id)
        _logger.debug(f'Retrieving page with id `{page_id}`.')
        data = self.raw_api.retrieve(page_id)
        return Page.model_validate(data)

    # https://developers.notion.com/reference/patch-page
    def update(self, page: Page, **properties: PropertyValue) -> None:
        """Update the Page object properties on the server."""
        page_id = raise_unset(page.id)
        _logger.debug(f'Updating info on page with id `{page_id}`.')
        props = {name: value.serialize_for_api() if value is not None else None for name, value in properties.items()}
        data = cast(dict[str, Any], self.raw_api.update(page_id.hex, properties=props))
        page.update(**data)

    def set_attr(
        self,
        page: Page,
        *,
        cover: FileObject | UnsetType | None = Unset,
        icon: FileObject | EmojiObject | CustomEmojiObject | UnsetType | None = Unset,
        in_trash: bool | UnsetType = Unset,
    ) -> None:
        """Set specific page attributes (such as cover, icon, etc.) on the server.

        `page` may be any suitable `PageRef` type.

        To remove an attribute, set its value to None.
        """
        page_id = PageRef.build(page).page_id
        props: dict[str, Any] = {}

        if cover is not Unset:
            if cover is None:
                _logger.debug(f'Removing cover from page with id `{page_id}`.')
                props['cover'] = None
            else:
                _logger.debug(f'Setting cover on page with id `{page_id}`.')
                props['cover'] = cover.serialize_for_api()  # type: ignore[union-attr]

        if icon is not Unset:
            if icon is None:
                _logger.debug(f'Removing icon from page with id `{page_id}`.')
                props['icon'] = None
            else:
                _logger.debug(f'Setting icon on page with id `{page_id}`.')
                props['icon'] = icon.serialize_for_api()  # type: ignore[union-attr]

        if in_trash is not Unset:
            if in_trash:
                _logger.debug(f'Deleting page with id `{page_id}`.')
                props['archived'] = True
            else:
                _logger.debug(f'Restoring page with id `{page_id}`.')
                props['archived'] = False

        data = cast(dict[str, Any], self.raw_api.update(page_id.hex, **props))
        page.update(**data)


class SearchEndpoint(Endpoint):
    """Interface to the API 'search' endpoint."""

    # https://developers.notion.com/reference/post-search
    def __call__(self, text: str | None = None) -> SearchQueryBuilder:
        """Perform a search with the optional text"""
        return SearchQueryBuilder(endpoint=self.api.client.search, text=text)


class UsersEndpoint(Endpoint):
    """Interface to the API 'users' endpoint."""

    @property
    def raw_api(self) -> NCUsersEndpoint:
        """Return the underlying endpoint in the Notion SDK"""
        return self.api.client.users

    # https://developers.notion.com/reference/get-users
    def list(self) -> Iterator[User]:
        """Return an iterator for all users in the workspace."""
        _logger.debug('Retrieving all known users.')
        user_iter = EndpointIterator[User](endpoint=self.raw_api.list)
        return user_iter()

    # https://developers.notion.com/reference/get-user
    def retrieve(self, user: User | UUID | str) -> User:
        """Return the User with the given ID."""
        user_id = str(UserRef.build(user).id)
        _logger.debug(f'Retrieving user with id `{user_id}`.')
        data = self.raw_api.retrieve(user_id)
        return User.model_validate(data)

    # https://developers.notion.com/reference/get-self
    def me(self) -> Bot:
        """Return the current bot User."""
        _logger.debug('Retrieving current integration bot')
        data = self.raw_api.me()
        return Bot.model_validate(data)


class CommentsEndpoint(Endpoint):
    """Interface to the API 'comments' endpoint."""

    @property
    def raw_api(self) -> NCCommentsEndpoint:
        """Return the underlying endpoint in the Notion SDK"""
        return self.api.client.comments

    # https://developers.notion.com/reference/create-a-comment
    def create(self, page: Page | UUID | str, rich_text: list[RichTextBaseObject]) -> Comment:
        """Create a comment on the specified Page."""
        page_ref = PageRef.build(page)
        _logger.debug(f'Creating a comment on page with id `{page_ref.page_id}.')
        rich_text_json = [rt.serialize_for_api() for rt in rich_text]
        data = self.raw_api.create(parent=page_ref.serialize_for_api(), rich_text=rich_text_json)
        return Comment.model_validate(data)

    # https://developers.notion.com/reference/create-a-comment
    def append(self, discussion_id: UUID | str, rich_text: list[RichTextBaseObject]) -> Comment:
        """Append a comment to the specified discussion."""
        _logger.debug(f'Appending a comment to discussion with id `{discussion_id}`.')
        rich_text_json = [rt.serialize_for_api() for rt in rich_text]
        data = self.raw_api.create(discussion_id=str(discussion_id), rich_text=rich_text_json)
        return Comment.model_validate(data)

    # https://developers.notion.com/reference/retrieve-a-comment
    def list(self, block: Block | Page | UUID | str) -> Iterator[Comment]:
        """Return all comments on the specified page or block."""
        block_id = str(ObjectRef.build(block).id)
        _logger.debug(f'Listing comments on block with id `{block_id}`.')
        comment_iter = EndpointIterator[Comment](endpoint=self.raw_api.list)
        return comment_iter(block_id=block_id)


class UploadsEndpoint(Endpoint):
    """Interface to the API 'file uploads' endpoint."""

    @property
    def raw_api(self) -> NCFileUploadsEndpoint:
        """Return the underlying endpoint in the Notion SDK"""
        return self.api.client.file_uploads

    # https://developers.notion.com/reference/create-a-file-upload
    def create(
        self,
        name: str | None = None,
        n_parts: int | None = None,
        mode: FileUploadMode = FileUploadMode.SINGLE_PART,
        external_url: str | None = None,
        content_type: str | None = None,
    ) -> FileUpload:
        """Create a file upload."""
        _logger.debug(f'Creating a file upload with mode `{mode}`.')
        kwargs = {
            'filename': name,
            'number_of_parts': n_parts,
            'mode': mode.value,
            'external_url': external_url,
            'content_type': content_type,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}  # Notion API doesn't like nulls
        data = self.raw_api.create(**kwargs)
        return FileUpload.model_validate(data)

    # https://developers.notion.com/reference/send-a-file-upload
    def send(self, file_upload: FileUpload, file: BinaryIO, part: int | None = None) -> None:
        """Send a file upload and update the file_upload object."""
        _logger.debug(f'Sending file upload with id `{file_upload.id}`.')
        # Notion API doesn't like nulls, so we eliminate them
        kwargs = {k: v for k, v in (('file', file), ('part_number', part)) if v is not None}
        data = cast(dict[str, Any], self.raw_api.send(file_upload_id=str(file_upload.id), **kwargs))
        file_upload.update(**data)

    # https://developers.notion.com/reference/complete-a-file-upload
    def complete(self, file_upload: FileUpload) -> None:
        """Complete the file upload and update the file_upload object."""
        _logger.debug(f'Completing file upload with id `{file_upload.id}`.')
        data = cast(dict[str, Any], self.raw_api.complete(file_upload_id=str(file_upload.id)))
        file_upload.update(**data)

    # https://developers.notion.com/reference/retrieve-a-file-upload
    def retrieve(self, upload_id: UUID | str) -> FileUpload:
        """Return the FileUpload with the given ID."""
        _logger.debug(f'Retrieving file upload with id `{upload_id}`.')
        data = self.raw_api.retrieve(file_upload_id=str(upload_id))
        return FileUpload.model_validate(data)

    # https://developers.notion.com/reference/list-file-uploads
    def list(self, status: FileUploadStatus | None = None, page_size: int = 100) -> Iterator[FileUpload]:
        """Return all file uploads."""
        file_upload_iter = EndpointIterator[FileUpload](endpoint=self.raw_api.list)
        kwargs: dict[str, Any] = {'page_size': page_size}
        if status is not None:
            kwargs['status'] = status.value
            suffix = f' filtering by status {status.value}'
        else:
            suffix = '.'
        _logger.debug(f'Listing all file uploads{suffix}')
        return file_upload_iter(**kwargs)

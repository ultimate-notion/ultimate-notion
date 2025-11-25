"""Functionality to initialize a Notion Session."""

from __future__ import annotations

import io
import logging
import os
import time
from collections.abc import Sequence
from threading import RLock
from types import TracebackType
from typing import Any, BinaryIO, ClassVar, cast
from uuid import UUID

import httpx
import notion_client
from notion_client.errors import APIResponseError

from ultimate_notion.blocks import Block, DataObject, _append_block_chunks, _chunk_blocks_for_api
from ultimate_notion.config import Config, activate_debug_mode, get_or_create_cfg
from ultimate_notion.database import DataSource
from ultimate_notion.emoji import CustomEmoji, Emoji
from ultimate_notion.errors import SessionError, UnknownDataSourceError, UnknownPageError, UnknownUserError
from ultimate_notion.file import MAX_FILE_SIZE, AnyFile, UploadedFile, get_file_size, get_mime_type
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import create_notion_client
from ultimate_notion.obj_api import query as obj_query
from ultimate_notion.obj_api.core import raise_unset
from ultimate_notion.obj_api.endpoints import NotionAPI
from ultimate_notion.obj_api.enums import FileUploadMode, FileUploadStatus
from ultimate_notion.obj_api.objects import get_uuid
from ultimate_notion.page import Page
from ultimate_notion.props import Title
from ultimate_notion.rich_text import Text
from ultimate_notion.schema import DefaultSchema, Schema
from ultimate_notion.user import Bot, UnknownUser, User
from ultimate_notion.utils import SList

_logger = logging.getLogger(__name__)


class Session:
    """A session for the Notion API.

    The session keeps tracks of all objects, e.g. pages, databases, etc.
    in an object store to avoid unnecessary calls to the API.
    """

    client: notion_client.Client
    api: NotionAPI
    _active_session: Session | None = None
    _lock = RLock()
    _own_bot_id: UUID | None = None
    cache: ClassVar[dict[UUID, DataObject | User]] = {}

    def __init__(self, cfg: Config | None = None, *, client: notion_client.Client | None = None, **kwargs: Any):
        """Initialize the `Session` object and the raw `api` endpoints.

        Args:
            cfg: configuration object
            **kwargs: Arguments for the [Notion SDK Client](https://ramnes.github.io/notion-sdk-py/reference/client/)
        """
        cfg = get_or_create_cfg() if cfg is None else cfg

        Session._initialize_once(self)

        if cfg.ultimate_notion.debug:
            activate_debug_mode()

        self.client = create_notion_client(cfg, **kwargs) if client is None else client
        self.api = NotionAPI(self.client)

    @classmethod
    def _initialize_once(cls, instance: Session) -> None:
        _logger.info('Initializing Notion session.')
        with Session._lock:
            if Session._active_session and Session._active_session is not instance:
                msg = 'Cannot initialize multiple Sessions at once'
                raise ValueError(msg)
            else:
                Session._active_session = instance

    @classmethod
    def get_active(cls) -> Session:
        """Return the current active session or None."""
        with Session._lock:
            if Session._active_session:
                return Session._active_session
            else:
                msg = 'There is no activate Session'
                raise ValueError(msg)

    @classmethod
    def get_or_create(cls, *args: Any, **kwargs: Any) -> Session:
        """Return the current active session or create a new session."""
        with Session._lock:
            if Session._active_session:
                return Session._active_session
            else:
                return cls(*args, **kwargs)

    def __enter__(self) -> Session:
        # Do nothing here as `__init__` created a client already and calling
        # `self.client.__enter__()` would initialize another client internally
        return self

    def __exit__(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the session and release resources."""
        _logger.info('Closing connection to Notion.')
        self.client.close()
        Session._active_session = None
        Session.cache.clear()
        Session._own_bot_id = None

    def is_closed(self) -> bool:
        """Determine if the session is closed or not."""
        try:
            self.raise_for_status()
        except RuntimeError:  # used by httpx client in case of closed connection
            return True
        else:
            return False

    def raise_for_status(self) -> None:
        """Confirm that the session is active and raise otherwise.

        Raises SessionError if there is a problem, otherwise returns None.
        """
        _logger.info('Checking connection to Notion.')
        try:
            self.whoami()
        except httpx.ConnectError as err:
            msg = 'Unable to connect to Notion'
            raise SessionError(msg) from err
        except APIResponseError as err:
            msg = 'Invalid API reponse'
            raise SessionError(msg) from err

    def get_block(self, block_ref: UUID | str, *, use_cache: bool = True) -> Block:
        """Retrieve a single block by an object reference."""
        block_uuid = get_uuid(block_ref)
        if use_cache and block_uuid in self.cache:
            _logger.info(f'Retrieving cached block with id `{block_uuid}`.')
            block = cast(Block, self.cache[block_uuid])
        else:
            _logger.info(f'Retrieving block with id `{block_uuid}`.')
            block = Block.wrap_obj_ref(self.api.blocks.retrieve(block_uuid))
            self.cache[block.id] = block
        _logger.info(f'Retrieved `{type(block)}` block.')
        return block

    def create_ds(
        self, parent: Page, *, schema: type[Schema] | None = None, title: str | None = None, inline: bool = False
    ) -> DataSource:
        """Create a new data source within a page.

        In case a title and a schema are provided, title overrides the schema's `db_title` attribute if it exists.
        """
        # Implementation:
        # 1. create the data source using a Notion API call and potential external forward relations
        # 2. initialize self-referencing forward relations
        # 3. create properties with self-referencing forward relations using an update call
        # 4. update the backward references, i.e. two-way relations, using an update call
        if title is not None:
            title = Text(title)
        elif schema is not None and schema._db_title is not None:
            title = schema._db_title
        else:
            title = None  # Anonymous data source without a title.

        ds_schema: type[Schema] = cast(type[Schema], DefaultSchema) if schema is None else schema
        _logger.info(f'Creating data source `{title or "<NoTitle>"}` in `{parent.title}` with schema:\n{ds_schema}')

        title_obj = title.obj_ref if title is not None else None
        schema_dct = {prop.name: prop.obj_ref for prop in ds_schema.get_props() if prop._is_init_ready}
        ds_obj = self.api.data_sources.create(parent=parent.obj_ref, title=title_obj, schema=schema_dct, inline=inline)

        ds: DataSource = DataSource.wrap_obj_ref(ds_obj)

        if schema:
            if schema._db_desc:
                self.api.data_sources.update(ds_obj, description=schema._db_desc.obj_ref)
            ds._set_schema(schema, during_init=True)  # schema is thus bound to the data source
            schema._init_self_refs()
            schema._init_self_ref_rollups()
            schema._update_bwd_rels()

        self.cache[ds.id] = ds
        return ds

    def create_dss(self, parents: Page | list[Page], schemas: list[type[Schema]]) -> list[DataSource]:
        """Create new data sources in the right order in case there are relations between them."""
        # ToDo: Implement
        raise NotImplementedError

    def search_ds(
        self, name: str | None = None, *, exact: bool = True, reverse: bool = False, deleted: bool = False
    ) -> SList[DataSource]:
        """Search a data source by name or return all if `name` is None.

        Args:
            name: name/title of the data source, return all if `None`
            exact: perform an exact search, not only a substring match
            reverse: search in the reverse order, i.e. the least recently edited results first
            deleted: include deleted data sources in search
        """
        _logger.info(f'Searching for data source with name `{name}`.')
        query = cast(
            obj_query.SearchQueryBuilder[obj_blocks.DataSource],
            self.api.search(name).filter(datasource_only=True),
        )
        if reverse:
            query.sort(ascending=True)
        data_sources = [
            cast(DataSource, self.cache.setdefault(raise_unset(ds.id), DataSource.wrap_obj_ref(ds)))
            for ds in query.execute()
        ]
        if exact and name is not None:
            data_sources = [ds for ds in data_sources if ds.title == name]
        if not deleted:
            data_sources = [ds for ds in data_sources if not ds.is_deleted]
        return SList(data_sources)

    def get_ds(self, ds_ref: UUID | str, *, use_cache: bool = True) -> DataSource:
        """Retrieve Notion data source by uuid."""
        ds_uuid = get_uuid(ds_ref)
        if use_cache and ds_uuid in self.cache:
            _logger.info(f'Retrieving cached data source with id `{ds_uuid}`.')
            ds = cast(DataSource, self.cache[ds_uuid])
        else:
            _logger.info(f'Retrieving data source with id `{ds_uuid}`.')
            try:
                ds = DataSource.wrap_obj_ref(self.api.data_sources.retrieve(ds_uuid))
            except APIResponseError as e:
                msg = f'Data source with id `{ds_uuid}` does not exist or is not accessible!'
                _logger.warning(msg)
                raise UnknownDataSourceError(msg) from e
            self.cache[ds.id] = ds
        _logger.info(f'Retrieved data source `{ds.title}`.')
        return ds

    def get_or_create_ds(self, parent: Page, schema: type[Schema]) -> DataSource:
        """Get or create the data source."""
        data_sources = SList(ds for ds in self.search_ds(schema._db_title) if ds.parent == parent)
        if len(data_sources) == 0:
            ds = self.create_ds(parent, schema=schema)
            while not [ds for ds in self.search_ds(schema._db_title) if ds.parent == parent]:
                _logger.info(f'Waiting for data source `{ds.title}` to be fully created.')
                time.sleep(1)
            return ds
        else:
            ds = data_sources.item()
            ds.schema = schema
            return ds

    def search_page(self, title: str | None = None, *, exact: bool = True, reverse: bool = False) -> SList[Page]:
        """Search a page by name. Deleted pages, i.e. in trash, are not included in the search.

        Args:
            title: title of the page, return all if `None`
            exact: perform an exact search, not only a substring match
            reverse: search in the reverse order, i.e. the least recently edited results first
        """
        _logger.info(f'Searching for page with title `{title}`.')
        query = cast(obj_query.SearchQueryBuilder[obj_blocks.Page], self.api.search(title).filter(page_only=True))
        if reverse:
            query.sort(ascending=True)
        pages = [
            cast(Page, self.cache.setdefault(raise_unset(page_obj.id), Page.wrap_obj_ref(page_obj)))
            for page_obj in query.execute()
        ]
        if exact and title is not None:
            pages = [page for page in pages if page.title == title]
        return SList(pages)

    def get_page(self, page_ref: UUID | str, *, use_cache: bool = True) -> Page:
        """Retrieve a page by uuid."""
        page_uuid = get_uuid(page_ref)
        if use_cache and page_uuid in self.cache:
            _logger.info(f'Retrieving cached page with id `{page_uuid}`.')
            page = cast(Page, self.cache[page_uuid])
        else:
            _logger.info(f'Retrieving page with id `{page_uuid}`.')
            try:
                page = Page.wrap_obj_ref(self.api.pages.retrieve(page_uuid))
            except APIResponseError as e:
                msg = f'Page with id {page_uuid} does not exist or is not accessible!'
                _logger.warning(msg)
                raise UnknownPageError(msg) from e
            self.cache[page.id] = page
        _logger.info(f'Retrieved page `{page.title}`.')
        return page

    def create_page(
        self,
        parent: Page | DataSource,
        title: Text | str | None = None,
        blocks: Sequence[Block] | None = None,
        *,
        cover: AnyFile | None = None,
        icon: AnyFile | Emoji | CustomEmoji | str | None = None,
    ) -> Page:
        """Create a new page in a `parent` page or data source with a given `title`.

        The `blocks` are optional and can be used to create a page with content right away.
        Note that some nested blocks may not be supported by the API and must be created separately, i.e.
        with an `append` call to a given block.
        """
        _logger.info(f'Creating page with title `{title}` in parent `{parent.title}`.')
        title_obj = title if title is None else Title(title).obj_ref
        cover_obj = None if cover is None else cover.obj_ref

        if isinstance(icon, str) and not isinstance(icon, Emoji | CustomEmoji):
            icon = Emoji(icon)
        icon_obj = None if icon is None else icon.obj_ref

        # We don't use the `children` parameter as we would need to call `list` afterwards to get the children,
        # in order to initialize them, which would be another API call. So we append the blocks manually here.
        page = Page.wrap_obj_ref(
            self.api.pages.create(parent=parent.obj_ref, title=title_obj, cover=cover_obj, icon=icon_obj)
        )
        self.cache[page.id] = page

        if blocks:
            blocks_iter = _chunk_blocks_for_api(page, blocks)
            _append_block_chunks(blocks_iter)

        return page

    def get_or_create_page(self, parent: Page | DataSource, title: str | None = None) -> Page:
        """Get an existing page or create a new one if it doesn't exist."""
        pages = SList(page for page in self.search_page(title) if page.parent == parent)
        if len(pages) == 0:
            page = self.create_page(parent, title=title)
            while not [page for page in self.search_page(title) if page.parent == parent]:
                _logger.info(f'Waiting for page `{page.title}` to be fully created.')
                time.sleep(1)
            return page
        else:
            return pages.item()

    def get_user(self, user_ref: UUID | str, *, use_cache: bool = True, raise_on_unknown: bool = True) -> User:
        """Get a user by uuid.

        In case the user is not found and `raise_on_unknown` is `False`, an `User` object is returned
        with the name `Unknown User`, where the property `is_unknown` is set to `True`.

        !!! warning

            Trying to retrieve yourself, i.e. the bot integration, only works if `use_cache` is true,
            since the low-level api, i.e. `api.users.retrieve()` does not work for the bot integration.
            Better use `whoami()` to get the bot integration user object.
        """
        user_uuid = get_uuid(user_ref)
        self.whoami()  # make sure cache is filled with the uuid of the bot integration

        if use_cache and user_uuid in self.cache:
            _logger.info(f'Retrieving cached user with id `{user_uuid}`.')
            user = cast(User, self.cache[user_uuid])
        else:
            _logger.info(f'Retrieving user with id `{user_uuid}`.')
            try:
                user_obj = self.api.users.retrieve(user_uuid)
            except APIResponseError as e:
                msg = f'User with id {user_uuid} not found!'
                _logger.warning(msg)
                if raise_on_unknown:
                    raise UnknownUserError(msg) from e
                else:  # we do not cache!
                    return UnknownUser(id=user_uuid)
            user = User.wrap_obj_ref(user_obj)
            self.cache[user.id] = user

        _logger.info(f'Retrieved user `{user}`.')
        return user

    def search_user(self, name: str) -> SList[User]:
        """Search a user by name."""
        _logger.info(f'Searching for user with name `{name}`.')
        return SList(user for user in self.all_users() if user.name == name)

    def all_users(self) -> list[User]:
        """Retrieve all users of this workspace."""
        _logger.info('Retrieving all users.')
        return [cast(User, self.cache.setdefault(user.id, User.wrap_obj_ref(user))) for user in self.api.users.list()]

    def whoami(self) -> Bot:
        """Return the integration as bot object."""
        _logger.info('Retrieving information about this integration bot.')
        if self._own_bot_id is None:
            user = self.api.users.me()
            self._own_bot_id = user.id
            return cast(Bot, self.cache.setdefault(user.id, Bot.wrap_obj_ref(user)))
        else:
            return cast(Bot, self.cache[self._own_bot_id])

    def upload(self, file: BinaryIO, *, file_name: str | None = None, mime_type: str | None = None) -> UploadedFile:
        """Upload a file to Notion."""
        file_name = file_name if file_name is not None else os.path.basename(getattr(file, 'name', 'unknown_file'))
        mime_type = mime_type if mime_type is not None else get_mime_type(file)
        file_size = get_file_size(file)
        if mime_type == 'application/octet-stream':
            _logger.warning(f'File `{file_name}` has unknown MIME type, falling back to text/plain.')
            mime_type = 'text/plain'  # Notion does not support application/octet-stream
        mode = FileUploadMode.SINGLE_PART if file_size <= MAX_FILE_SIZE else FileUploadMode.MULTI_PART
        _logger.info(
            f'Uploading file `{file_name}` of size {file_size} bytes with MIME type `{mime_type}` in mode `{mode}`.'
        )
        n_parts = -(-file_size // MAX_FILE_SIZE)  # ceiling division
        file_upload_obj = self.api.uploads.create(
            name=file_name, n_parts=None if n_parts == 1 else n_parts, mode=mode, content_type=mime_type
        )

        if mode == FileUploadMode.SINGLE_PART:
            self.api.uploads.send(file_upload=file_upload_obj, file=file)
        else:
            for part in range(1, n_parts + 1):
                _logger.info(f'Uploading part {part}/{n_parts} of file `{file_name}`.')
                chunk = file.read(MAX_FILE_SIZE)
                self.api.uploads.send(file_upload=file_upload_obj, part=part, file=io.BytesIO(chunk))
            self.api.uploads.complete(file_upload=file_upload_obj)

        return UploadedFile.from_file_upload(file_upload_obj)

    def import_url(self, url: str, file_name: str, *, block: bool = True) -> UploadedFile:
        """Import a file from a URL."""
        _logger.info(f'Importing file from URL `{url}`.')
        file_upload_obj = self.api.uploads.create(name=file_name, mode=FileUploadMode.EXTERNAL_URL, external_url=url)
        file_upload = UploadedFile.from_file_upload(file_upload_obj)
        if block:
            file_upload.wait_until_uploaded()
        return file_upload

    def list_uploads(self, filter: FileUploadStatus | None = None) -> list[UploadedFile]:  # noqa: A002
        """List all uploaded files and optionally filter by status."""
        _logger.info('Listing all uploaded files.')
        return [UploadedFile.from_file_upload(upload) for upload in self.api.uploads.list(status=filter)]

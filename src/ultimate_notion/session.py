"""Functionality to initialize a Notion Session."""

from __future__ import annotations

import logging
import time
from threading import RLock
from types import TracebackType
from typing import Any, ClassVar, cast
from uuid import UUID

import httpx
import notion_client
from notion_client.errors import APIResponseError

from ultimate_notion.blocks import Block, DataObject
from ultimate_notion.config import Config, activate_debug_mode, get_or_create_cfg
from ultimate_notion.database import Database
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import create_notion_client
from ultimate_notion.obj_api import query as obj_query
from ultimate_notion.obj_api.endpoints import NotionAPI
from ultimate_notion.obj_api.objects import UnknownUser as UnknownUserObj
from ultimate_notion.obj_api.objects import get_uuid
from ultimate_notion.page import Page
from ultimate_notion.props import Title
from ultimate_notion.rich_text import Text
from ultimate_notion.schema import DefaultSchema, Schema
from ultimate_notion.user import User
from ultimate_notion.utils import SList

_logger = logging.getLogger(__name__)


class SessionError(Exception):
    """Raised when there are issues with the Notion session."""


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
    def _initialize_once(cls, instance: Session):
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
    def get_or_create(cls, *args, **kwargs) -> Session:
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

    def close(self):
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

    def raise_for_status(self):
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

    # ToDo: Provide a title and description for the database that overwrites the values from the schema
    def create_db(self, parent: Page, schema: type[Schema] | None = None) -> Database:
        """Create a new database within a page."""
        # Implementation:
        # 1. initialize external forward relations, i.e. relations pointing to other databases
        # 2. create the database using a Notion API call and potential external forward relations
        # 3. initialize self-referencing forward relations
        # 4. create properties with self-referencing forward relations using an update call
        # 5. update the backward references, i.e. two-way relations, using an update call
        if schema:
            _logger.info(f'Creating database `{schema.db_title}` in page `{parent.title}` with schema:\n{schema}')
            schema._init_fwd_rels()
            schema_dct = {prop.name: prop.type.obj_ref for prop in schema._get_init_props()}
            title = schema.db_title.obj_ref if schema.db_title is not None else None
            db_obj = self.api.databases.create(parent=parent.obj_ref, title=title, schema=schema_dct)
            if schema.db_desc:
                db_obj = self.api.databases.update(db_obj, description=schema.db_desc.obj_ref)
        else:
            _logger.info(f'Creating database in page `{parent.title}` with default schema.')
            schema_dct = {prop.name: prop.type.obj_ref for prop in DefaultSchema._get_init_props()}
            db_obj = self.api.databases.create(parent=parent.obj_ref, schema=schema_dct)

        db: Database = Database.wrap_obj_ref(db_obj)

        if schema:
            db._set_schema(schema, during_init=True)  # schema is thus bound to the database
            schema._init_self_refs()
            schema._init_self_ref_rollups()
            schema._update_bwd_rels()

        self.cache[db.id] = db
        return db

    def create_dbs(self, parents: Page | list[Page], schemas: list[type[Schema]]) -> list[Database]:
        """Create new databases in the right order in case there a relations between them."""
        # ToDo: Implement
        raise NotImplementedError

    def search_db(
        self, db_name: str | None = None, *, exact: bool = True, reverse: bool = False, deleted: bool = False
    ) -> SList[Database]:
        """Search a database by name or return all if `db_name` is None.

        Args:
            db_name: name/title of the database, return all if `None`
            exact: perform an exact search, not only a substring match
            reverse: search in the reverse order, i.e. the least recently edited results first
            deleted: include deleted databases in search
        """
        _logger.info(f'Searching for database with name `{db_name}`.')
        query: obj_query.SearchQueryBuilder[obj_blocks.Database] = self.api.search(db_name).filter(db_only=True)
        if reverse:
            query.sort(ascending=True)
        dbs = [cast(Database, self.cache.setdefault(db.id, Database.wrap_obj_ref(db))) for db in query.execute()]
        if exact and db_name is not None:
            dbs = [db for db in dbs if db.title == db_name]
        if not deleted:
            dbs = [db for db in dbs if not db.is_deleted]
        return SList(dbs)

    def get_db(self, db_ref: UUID | str, *, use_cache: bool = True) -> Database:
        """Retrieve Notion database by uuid"""
        db_uuid = get_uuid(db_ref)
        if use_cache and db_uuid in self.cache:
            _logger.info(f'Retrieving cached database with id `{db_uuid}`.')
            db = cast(Database, self.cache[db_uuid])
        else:
            _logger.info(f'Retrieving database with id `{db_uuid}`.')
            db = Database.wrap_obj_ref(self.api.databases.retrieve(db_uuid))
            self.cache[db.id] = db
        _logger.info(f'Retrieved database `{db.title}`.')
        return db

    def get_or_create_db(self, parent: Page, schema: type[Schema]) -> Database:
        """Get or create the database."""
        dbs = SList(db for db in self.search_db(schema.db_title) if db.parent == parent)
        if len(dbs) == 0:
            db = self.create_db(parent, schema)
            while not [db for db in self.search_db(schema.db_title) if db.parent == parent]:
                _logger.info(f'Waiting for database `{db.title}` to be fully created.')
                time.sleep(1)
            return db
        else:
            db = dbs.item()
            db.schema = schema
            return db

    def search_page(self, title: str | None = None, *, exact: bool = True, reverse: bool = False) -> SList[Page]:
        """Search a page by name. Deleted pages, i.e. in trash, are not included in the search.

        Args:
            title: title of the page, return all if `None`
            exact: perform an exact search, not only a substring match
            reverse: search in the reverse order, i.e. the least recently edited results first
        """
        _logger.info(f'Searching for page with title `{title}`.')
        query: obj_query.SearchQueryBuilder[obj_blocks.Page] = self.api.search(title).filter(page_only=True)
        if reverse:
            query.sort(ascending=True)
        pages = [
            cast(Page, self.cache.setdefault(page_obj.id, Page.wrap_obj_ref(page_obj))) for page_obj in query.execute()
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
            page = Page.wrap_obj_ref(self.api.pages.retrieve(page_uuid))
            self.cache[page.id] = page
        _logger.info(f'Retrieved page `{page.title}`.')
        return page

    def create_page(self, parent: Page | Database, title: Text | str | None = None) -> Page:
        """Create a new page in a parent page or database."""
        _logger.info(f'Creating page with title `{title}` in parent `{parent.title}`.')
        title_obj = title if title is None else Title(title).obj_ref
        page = Page.wrap_obj_ref(self.api.pages.create(parent=parent.obj_ref, title=title_obj))
        self.cache[page.id] = page
        return page

    def get_user(self, user_ref: UUID | str, *, use_cache: bool = True) -> User:
        """Get a user by uuid.

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
            except APIResponseError:
                _logger.warning(f'User with id {user_uuid} not found!')
                user_obj = UnknownUserObj(id=user_uuid, object='user', type='unknown')
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

    def whoami(self) -> User:
        """Return the user object of this bot."""
        _logger.info('Retrieving user of this integration.')
        if self._own_bot_id is None:
            user = self.api.users.me()
            self._own_bot_id = user.id
            return cast(User, self.cache.setdefault(user.id, User.wrap_obj_ref(user)))
        else:
            return cast(User, self.cache[self._own_bot_id])

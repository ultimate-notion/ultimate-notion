"""Session object"""
from __future__ import annotations

import logging
import os
from threading import RLock
from types import TracebackType
from typing import Any
from uuid import UUID

from httpx import ConnectError
from notion_client.errors import APIResponseError

from ultimate_notion.record import Record
from ultimate_notion.blocks import Block
from ultimate_notion.database import Database
from ultimate_notion.obj_api import blocks, types
from ultimate_notion.obj_api.session import Session as NotionalSession
from ultimate_notion.page import Page
from ultimate_notion.schema import PageSchema, Relation
from ultimate_notion.user import User
from ultimate_notion.utils import ObjRef, SList, get_uuid

_log = logging.getLogger(__name__)
ENV_NOTION_AUTH_TOKEN = 'NOTION_AUTH_TOKEN'


class SessionError(Exception):
    """Raised when there are issues with the Notion session."""

    def __init__(self, message):
        """Initialize the `SessionError` with a supplied message."""
        super().__init__(message)


class Session:
    """A session for the Notion API

    The session keeps tracks of all objects, e.g. pages, databases, etc. in an object store to avoid unnecessary calls to the API.
    Use an explicit `.refresh()` to update an object.
    """

    _active_session: Session | None = None
    _lock = RLock()
    # todo: have different stores for different types
    _object_store: dict[UUID, Record] = {}

    def __init__(self, auth: str | None = None, **kwargs: Any):
        """Initialize the `Session` object and the Notional endpoints.

        Args:
            auth: secret token from the Notion integration
            **kwargs: Arguments for the [Notion SDK Client][https://ramnes.github.io/notion-sdk-py/reference/client/]
        """
        if auth is None:
            if (env_token := os.getenv(ENV_NOTION_AUTH_TOKEN)) is not None:
                auth = env_token
            else:
                msg = f'Either pass `auth` or set {ENV_NOTION_AUTH_TOKEN}'
                raise RuntimeError(msg)

        _log.debug('Initializing Notion session...')
        Session._initialize_once(self)
        # Todo: Put this in `obj_api` name-space instead with just the endpoinds. Use client instead of session.
        # So have an ObjAPI class that initializes the client int NotionalSession
        self.notional = NotionalSession(auth=auth, **kwargs)
        _log.info('Initialized Notion session')

    @classmethod
    def _initialize_once(cls, instance: Session):
        with Session._lock:
            if Session._active_session and Session._active_session is not instance:
                msg = 'Cannot initialize multiple Sessions at once'
                raise ValueError(msg)
            else:
                Session._active_session = instance

    @classmethod
    def get_active(cls):
        """Return the current active session or raise"""
        with Session._lock:
            if Session._active_session:
                return Session._active_session
            else:
                msg = 'There is no activate Session'
                raise ValueError(msg)

    def __enter__(self) -> Session:
        _log.debug('Connecting to Notion...')
        self.notional.client.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        _log.debug('Closing connection to Notion...')
        self.notional.client.__exit__(exc_type, exc_value, traceback)
        Session._active_session = None
        Session._object_store.clear()

    def close(self):
        """Close the session and release resources."""
        self.notional.client.close()
        Session._active_session = None
        Session._object_store.clear()

    def raise_for_status(self):
        """Confirm that the session is active and raise otherwise.

        Raises SessionError if there is a problem, otherwise returns None.
        """
        try:
            me = self.whoami()
        except ConnectError as err:
            msg = 'Unable to connect to Notion'
            raise SessionError(msg) from err
        except APIResponseError as err:
            msg = 'Invalid API reponse'
            raise SessionError(msg) from err
        if me is None:
            msg = 'Unable to get current user'
            raise SessionError(msg)

    def create_db(self, parent: Page, schema: PageSchema | type[PageSchema] | None) -> Database:
        """Create a new database"""
        if schema:
            schema._init_forward_relations()
            schema_no_backrels_dct = {
                name: prop_type
                for name, prop_type in schema.to_dict().items()
                if not (isinstance(prop_type, Relation) and not prop_type.schema)
            }
            schema_dct = {k: v.obj_ref for k, v in schema_no_backrels_dct.items()}
        else:
            schema_dct = {}

        db_obj = self.notional.databases.create(parent=parent.obj_ref, title=schema.db_title, schema=schema_dct)
        db = Database(obj_ref=db_obj)

        if schema:
            db.schema = schema
            schema._init_backward_relations()

        self._object_store[db.id] = db
        return db

    def create_dbs(self, parents: Page | list[Page], schemas: list[type[PageSchema]]) -> list[Database]:
        pass

    def ensure_db(self, parent: Page, schema: type[PageSchema], title: str | None = None):
        """Get or create the database"""
        # TODO: Implement

    def search_db(self, db_name: str | None = None, *, exact: bool = True) -> SList[Database]:
        """Search a database by name

        Args:
            db_name: name/title of the database, return all if `None`
            exact: perform an exact search, not only a substring match
        """
        query = self.notional.search(db_name).filter(property='object', value='database')
        dbs = SList(self._object_store.get(db.id, Database(obj_ref=db)) for db in query.execute())
        if exact and db_name is not None:
            dbs = SList(db for db in dbs if db.title == db_name)
        return dbs

    def _get_db(self, db_uuid: UUID) -> Database:
        """Retrieve database circumenventing the session cache"""
        return Database(obj_ref=self.notional.databases.retrieve(db_uuid))

    def get_db(self, db_ref: ObjRef) -> Database:
        """Retrieve Notion database by uuid"""
        db_uuid = get_uuid(db_ref)
        if db_uuid in self._object_store:
            return self._object_store[db_uuid]
        else:
            db = Database(obj_ref=self.notional.databases.retrieve(db_uuid))
            self._object_store[db.id] = db
            return db

    def search_page(self, title: str | None = None, *, exact: bool = True) -> SList[Page]:
        """Search a page by name

        Args:
            title: title of the page, return all if `None`
            exact: perform an exact search, not only a substring match
        """
        query = self.notional.search(title).filter(property='object', value='page')
        pages = SList(self._object_store.get(page.id, Page(obj_ref=page)) for page in query.execute())
        if exact and title is not None:
            pages = SList(page for page in pages if page.title == title)
        return pages

    def get_page(self, page_ref: ObjRef) -> Page:
        page_uuid = get_uuid(page_ref)
        if page_uuid in self._object_store:
            return self._object_store[page_uuid]
        else:
            page = Page(obj_ref=self.notional.pages.retrieve(page_uuid))
            self._object_store[page.id] = page
            return page

    def create_page(self, parent: Page, title: str | None = None) -> Page:
        page = Page(obj_ref=self.notional.pages.create(parent=parent.obj_ref, title=title))
        self._object_store[page.id] = page
        return page

    def _get_user(self, uuid: UUID) -> types.User:
        return self.notional.users.retrieve(uuid)

    def get_user(self, user_ref: ObjRef) -> User:
        user_uuid = get_uuid(user_ref)
        return User(obj_ref=self._get_user(user_uuid))

    def whoami(self) -> User:
        """Return the user object of this bot"""
        return self.notional.users.me()

    def all_users(self) -> list[User]:
        """Retrieve all users of this workspace"""
        return [User(obj_ref=user) for user in self.notional.users.list()]

    def get_block(self, block_ref: ObjRef):
        """Retrieve a block"""
        return Block(obj_ref=self.notional.blocks.retrieve(block_ref))

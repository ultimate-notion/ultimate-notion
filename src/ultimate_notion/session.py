"""Session object"""
from __future__ import annotations

import logging
import os
from threading import RLock
from types import TracebackType
from typing import Any
from uuid import UUID

from cachetools import TTLCache, cached
from httpx import ConnectError
from notion_client.errors import APIResponseError

from ultimate_notion.database import Database
from ultimate_notion.obj_api import blocks, types
from ultimate_notion.obj_api.session import Session as NotionalSession
from ultimate_notion.page import Page
from ultimate_notion.schema import PageSchema
from ultimate_notion.user import User
from ultimate_notion.utils import ObjRef, SList, get_uuid

_log = logging.getLogger(__name__)
ENV_NOTION_AUTH_TOKEN = 'NOTION_AUTH_TOKEN'


class SessionError(Exception):
    """Raised when there are issues with the Notion session."""

    def __init__(self, message):
        """Initialize the `NotionSessionError` with a supplied message."""
        super().__init__(message)


class Session:
    """A session for the Notion API

    This is a singleton
    """

    _active_session: Session | None = None
    _lock = RLock()

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
        Session._ensure_initialized(self)
        self.notional = NotionalSession(auth=auth, **kwargs)

        # prepare API methods for decoration
        self._search_db_unwrapped = self.search_db
        self._get_db_unwrapped = self._get_db
        self._get_page_unwrapped = self._get_page
        self._get_user_unwrapped = self._get_user
        self.set_cache()
        _log.info('Initialized Notion session')

    @classmethod
    def _ensure_initialized(cls, instance: Session):
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

    def set_cache(self, ttl=30, maxsize=1024):
        wrapper = cached(cache=TTLCache(maxsize=maxsize, ttl=ttl))
        self.search_db = wrapper(self._search_db_unwrapped)
        self._get_db = wrapper(self._get_db_unwrapped)
        self._get_page = wrapper(self._get_page_unwrapped)
        self._get_user = wrapper(self._get_user_unwrapped)

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

    def close(self):
        """Close the session and release resources."""
        self.notional.client.close()
        Session._active_session = None

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

    def create_db(self, parent: Page, schema: type[PageSchema], title: str | None = None) -> Database:
        """Create a new database"""
        schema_dct = {k: v.obj_ref for k, v in schema.to_dict().items()}
        db = self.notional.databases.create(parent=parent.obj_ref, title=title, schema=schema_dct)
        return Database(obj_ref=db)

    def ensure_db(self, parent: Page, schema: type[PageSchema], title: str | None = None):
        """Get or create the database"""
        # TODO: Implement

    def delete_db(self, db_ref: Database | ObjRef):
        db_uuid = db_ref.id if isinstance(db_ref, Database) else get_uuid(db_ref)
        self.notional.blocks.delete(db_uuid)

    def search_db(self, db_name: str | None = None, *, exact: bool = True) -> SList[Database]:
        """Search a database by name

        Args:
            db_name: name/title of the database, return all if `None`
            exact: perform an exact search, not only a substring match
        """
        query = self.notional.search(db_name).filter(property='object', value='database')
        dbs = SList(Database(obj_ref=db) for db in query.execute())
        if exact and db_name is not None:
            dbs = SList(db for db in dbs if db.title == db_name)
        return dbs

    def _get_db(self, uuid: UUID) -> blocks.Database:
        """Retrieve Notional database block by uuid

        This indirection is needed since more general object references are not hashable, which is needed for caching
        """
        return self.notional.databases.retrieve(uuid)

    def get_db(self, db_ref: ObjRef) -> Database:
        """Retrieve Notional database block by uuid"""
        db_uuid = get_uuid(db_ref)
        return Database(obj_ref=self._get_db(db_uuid))

    def search_page(self, title: str | None = None, *, exact: bool = True) -> SList[Page]:
        """Search a page by name

        Args:
            title: title of the page, return all if `None`
            exact: perform an exact search, not only a substring match
        """
        query = self.notional.search(title).filter(property='object', value='page')
        pages = SList(Page(obj_ref=page) for page in query.execute())
        if exact and title is not None:
            pages = SList(page for page in pages if page.title == title)
        return pages

    def _get_page(self, uuid: UUID) -> blocks.Page:
        """Retrieve Notional page by uuid

        This indirection is needed since more general object references are not hashable.
        """
        return self.notional.pages.retrieve(uuid)

    def get_page(self, page_ref: ObjRef) -> Page:
        page_uuid = get_uuid(page_ref)
        return Page(obj_ref=self._get_page(page_uuid))

    def create_page(self, parent: Page, title: str | None = None) -> Page:
        return Page(obj_ref=self.notional.pages.create(parent=parent.obj_ref, title=title))

    def delete_page(self, page: Page):
        self.notional.pages.delete(page.obj_ref)

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
        # ToDo: Implement me
        raise NotImplementedError

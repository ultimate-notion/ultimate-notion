"""Session object"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from types import TracebackType
from typing import Any
from uuid import UUID

from cachetools import TTLCache, cached
from httpx import ConnectError
from notion_client.errors import APIResponseError
from notional import blocks, types
from notional.session import Session as NotionalSession

from ultimate_notion.database import Database
from ultimate_notion.page import Page
from ultimate_notion.schema import PropertyObject
from ultimate_notion.user import User
from ultimate_notion.utils import ObjRef, SList, make_obj_ref

_log = logging.getLogger(__name__)
ENV_NOTION_AUTH_TOKEN = 'NOTION_AUTH_TOKEN'


class SessionError(Exception):
    """Raised when there are issues with the Notion session."""

    def __init__(self, message):
        """Initialize the `NotionSessionError` with a supplied message."""
        super().__init__(message)


class Session:
    """A session for the Notion API"""

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

        self.notional = NotionalSession(auth=auth, **kwargs)

        # prepare API methods for decoration
        self._search_db_unwrapped = self.search_db
        self._get_db_unwrapped = self._get_db
        self._get_page_unwrapped = self._get_page
        self._get_user_unwrapped = self._get_user
        self.set_cache()
        _log.info('Initialized Notion session')

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

    def close(self):
        """Close the session and release resources."""
        self.notional.client.close()

    def raise_for_status(self):
        """Confirm that the session is active and raise otherwise.

        Raises SessionError if there is a problem, otherwise returns None.
        """
        error = None

        try:
            me = self.whoami()

            if me is None:
                msg = 'Unable to get current user'
                raise SessionError(msg)
        except ConnectError:
            error = 'Unable to connect to Notion'
        except APIResponseError as err:
            error = str(err)

        if error is not None:
            raise SessionError(error)

    def create_db(self, parent_page: Page, schema: dict[str, PropertyObject], title=None) -> Database:
        """Create a new database"""
        schema = {k: v.obj_ref for k, v in schema.items()}
        db = self.notional.databases.create(parent=parent_page.obj_ref, title=title, schema=schema)
        return Database(db_ref=db, session=self)

    def delete_db(self, db: ObjRef | Database):
        """Delete a database"""
        db_uuid = db.id if isinstance(db, Database) else make_obj_ref(db).id
        return self.notional.blocks.delete(db_uuid)

    def search_db(
        self, db_name: str | None = None, *, exact: bool = True, parents: Iterable[str] | None = None
    ) -> SList[Database]:
        """Search a database by name

        Args:
            db_name: name/title of the database, return all if `None`
            exact: perform an exact search, not only a substring match
            parents: list of parent pages to further refine the search
        """
        if parents is not None:
            # ToDo: Implement a search that also considers the parents
            raise NotImplementedError

        query = self.notional.search(db_name).filter(property='object', value='database')
        dbs = SList(Database(db_ref=db, session=self) for db in query.execute())
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
        db_uuid = make_obj_ref(db_ref).id
        return Database(db_ref=self._get_db(db_uuid), session=self)

    def search_page(
        self, page_name: str | None = None, *, exact: bool = True, parents: Iterable[str] | None = None
    ) -> SList[Page]:
        """Search a page by name

        Args:
            page_name: name/title of the page, return all if `None`
            exact: perform an exact search, not only a substring match
            parents: list of parent pages to further refine the search
        """
        if parents is not None:
            # ToDo: Implement a search that also considers the parents
            raise NotImplementedError

        query = self.notional.search(page_name).filter(property='object', value='page')
        pages = SList(Page(page_ref=page, session=self) for page in query.execute())
        if exact and page_name is not None:
            pages = SList(page for page in pages if page.title == page_name)
        return pages

    def _get_page(self, uuid: UUID) -> blocks.Page:
        """Retrieve Notional page by uuid

        This indirection is needed since more general object references are not hashable.
        """
        return self.notional.pages.retrieve(uuid)

    def get_page(self, page_ref: ObjRef) -> Page:
        page_uuid = make_obj_ref(page_ref).id
        return Page(page_ref=self._get_page(page_uuid), session=self)

    def _get_user(self, uuid: UUID) -> types.User:
        return self.notional.users.retrieve(uuid)

    def get_user(self, user_ref: ObjRef) -> User:
        user_uuid = make_obj_ref(user_ref).id
        return User(obj_ref=self.notional.users.retrieve(user_uuid))

    def whoami(self) -> User:
        """Return the user object of this bot"""
        return self.notional.users.me()

    def all_users(self) -> list[User]:
        """Retrieve all users of this workspace"""
        return [User(obj_ref=user) for user in self.notional.users.list()]

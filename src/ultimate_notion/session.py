"""Session object

Replicates some parts of `notional.session` but the API is changed
"""
from __future__ import annotations

import logging
import os
from types import TracebackType
from typing import Optional, Type, Union
from uuid import UUID

import notion_client
from cachetools import TTLCache, cached
from httpx import ConnectError
from notion_client.errors import APIResponseError
from notional import types
from notional.session import BlocksEndpoint, DatabasesEndpoint, PagesEndpoint, SearchEndpoint, UsersEndpoint

from .database import Database
from .page import Page
from .user import User
from .utils import SList

_log = logging.getLogger(__name__)
ENV_NOTION_AUTH_TOKEN = "NOTION_AUTH_TOKEN"


class SessionError(Exception):
    """Raised when there are issues with the Notion session."""

    def __init__(self, message):
        """Initialize the `NotionSessionError` with a supplied message."""
        super().__init__(message)


class Session(object):
    """An active session with the Notion SDK."""

    def __init__(self, auth: Optional[str] = None, **kwargs):
        """Initialize the `Session` object and the endpoints.

        `kwargs` will be passed direction to the Notion SDK Client.  For more details,
        see the (full docs)[https://ramnes.github.io/notion-sdk-py/reference/client/].

        :param live_updates: changes will be propagated to Notion
        :param auth: bearer token for authentication
        """
        if auth is None:
            if (env_token := os.getenv(ENV_NOTION_AUTH_TOKEN)) is not None:
                auth = env_token
            else:
                raise RuntimeError(f"Either pass `auth` or set {ENV_NOTION_AUTH_TOKEN}")

        self.client = notion_client.Client(auth=auth, **kwargs)

        self.blocks = BlocksEndpoint(self)
        self.databases = DatabasesEndpoint(self)
        self.pages = PagesEndpoint(self)
        self.search = SearchEndpoint(self)
        self.users = UsersEndpoint(self)

        self._search_db = self.search_db
        self._get_db = self.get_db
        self._get_page = self.get_page
        self._get_user = self.get_user
        self.set_cache()
        _log.info("Initialized Notion session")

    def set_cache(self, ttl=30, maxsize=1024):
        wrapper = cached(cache=TTLCache(maxsize=maxsize, ttl=ttl))
        self.search_db = wrapper(self._search_db)
        self.get_db = wrapper(self._get_db)
        self.get_page = wrapper(self._get_page)
        self.get_user = wrapper(self._get_user)

    def __enter__(self) -> Session:
        _log.debug("Connecting to Notion...")
        self.client.__enter__()
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        _log.debug("Closing connection to Notion...")
        self.client.__exit__(exc_type, exc_value, traceback)

    def close(self):
        """Close the session and release resources."""
        self.client.close()

    def raise_for_status(self):
        """Confirm that the session is active and raise otherwise.

        Raises SessionError if there is a problem, otherwise returns None.
        """
        error = None

        try:
            me = self.users.me()

            if me is None:
                raise SessionError("Unable to get current user")
        except ConnectError:
            error = "Unable to connect to Notion"
        except APIResponseError as err:
            error = str(err)

        if error is not None:
            raise SessionError(error)

    def search_db(self, db_name: Optional[str] = None, exact: bool = True) -> SList[Database]:
        """Search a database by name

        Args:
            db_name: name/title of the database, return all if `None`
            exact: perform an exact search, not only a substring match
        """
        dbs = SList(
            Database(obj_ref=db, session=self)
            for db in self.search(db_name).filter(property="object", value="database").execute()
        )
        if exact and db_name is not None:
            dbs = SList(db for db in dbs if db.title == db_name)
        return dbs

    def get_db(self, db_id: Union[str, UUID]) -> Database:
        db_uuid = db_id if isinstance(db_id, UUID) else UUID(db_id)
        return Database(obj_ref=self.databases.retrieve(db_uuid), session=self)

    def get_page(self, page_id: Union[str, UUID]) -> Page:
        return Page(obj_ref=self.pages.retrieve(page_id), session=self)

    def get_user(self, user_id: Union[str, UUID]) -> types.User:
        return User(obj_ref=self.users.retrieve(user_id))

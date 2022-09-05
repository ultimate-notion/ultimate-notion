"""Session object"""
from __future__ import annotations

import logging
import os
from types import TracebackType
from typing import Type, Union
from uuid import UUID

import notion_client
from httpx import ConnectError
from notion_client.errors import APIResponseError

from .core.endpoints import (
    BlocksEndpoint,
    DatabasesEndpoint,
    PagesEndpoint,
    SearchEndpoint,
    UsersEndpoint,
)
from .database import Database
from .page import Page
from .utils import slist

_log = logging.getLogger(__name__)
ENV_NOTION_AUTH_TOKEN = "NOTION_AUTH_TOKEN"


class NotionSessionError(Exception):
    """Raised when there are issues with the Notion session."""

    def __init__(self, message):
        """Initialize the `NotionSessionError` with a supplied message."""
        super().__init__(message)


class NotionSession(object):
    """An active session with the Notion SDK."""

    def __init__(self, **kwargs):
        """Initialize the `Session` object and the endpoints.

        `kwargs` will be passed direction to the Notion SDK Client.  For more details,
        see the (full docs)[https://ramnes.github.io/notion-sdk-py/reference/client/].

        :param live_updates: changes will be propagated to Notion
        :param auth: bearer token for authentication
        """
        self.live_updates = kwargs.pop("live_updates", True)
        if (env_token := os.getenv(ENV_NOTION_AUTH_TOKEN)) is not None:
            kwargs.setdefault("auth", env_token)

        self.client = notion_client.Client(**kwargs)

        self.blocks = BlocksEndpoint(self)
        self.databases = DatabasesEndpoint(self)
        self.pages = PagesEndpoint(self)
        self.search = SearchEndpoint(self)
        self.users = UsersEndpoint(self)

        _log.info("Initialized Notion session")

    def __enter__(self) -> NotionSession:
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
                raise NotionSessionError("Unable to get current user")

        except ConnectError:
            error = "Unable to connect to Notion"

        except APIResponseError as err:
            error = str(err)

        if error is not None:
            raise NotionSessionError(error)

    def search_db(self, db_name: str) -> slist[Database]:
        return slist(
            Database(db_obj=db, session=self)
            for db in self.search(db_name)
            .filter(property="object", value="database")
            .execute()
        )

    def get_db(self, db_id: Union[str, UUID]) -> Database:
        db_uuid = db_id if isinstance(db_id, UUID) else UUID(db_id)
        return Database(db_obj=self.databases.retrieve(db_uuid), session=self)

    def get_page(self, page_id: Union[str, UUID]) -> Page:
        return Page(page_obj=self.pages.retrieve(page_id), session=self)

"""Session object"""
import logging
from types import TracebackType
from typing import Type

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

_log = logging.getLogger(__name__)


class SessionError(Exception):
    """Raised when there are issues with the Notion session."""

    def __init__(self, message):
        """Initialize the `SessionError` with a supplied message."""
        super().__init__(message)


class Session(object):
    """An active session with the Notion SDK."""

    def __init__(self, **kwargs):
        """Initialize the `Session` object and the endpoints.

        `kwargs` will be passed direction to the Notion SDK Client.  For more details,
        see the (full docs)[https://ramnes.github.io/notion-sdk-py/reference/client/].

        :param auth: bearer token for authentication
        """
        self.client = notion_client.Client(**kwargs)

        self.blocks = BlocksEndpoint(self)
        self.databases = DatabasesEndpoint(self)
        self.pages = PagesEndpoint(self)
        self.search = SearchEndpoint(self)
        self.users = UsersEndpoint(self)

        _log.info("Initialized Notion SDK client")

    def __enter__(self) -> "Session":
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

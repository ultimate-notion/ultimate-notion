"""Session object"""
import logging

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
        """Initialize the `SessionError` with a supplied message.."""
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

    @property
    def is_active(self):
        """Determine if the current session is active.

        The session is considered "active" if it has not been closed.  This does not
        determine if the session can connect to the Notion API.
        """
        return self.client is not None

    def close(self):
        """Close the session and release resources."""

        if self.client is None:
            raise SessionError("Session is not active.")

        self.client.close()
        self.client = None

    def ping(self):
        """Confirm that the session is active and able to connect to Notion.

        Raises SessionError if there is a problem, otherwise returns True.
        """

        if self.is_active is False:
            return False

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

        return True

"""Low-level object-oriented API for Notion.

This subpackage provides an object-oriented API for Notion by wrapping the JSON-structured
requests and responses of [notion-sdk-py] into Python objects using pydantic. Also paginated
result lists by the API are resolved automatically.

The code was taken originally from [Notional] by Jason Heddings and is MIT-licensed.
Due to the Pydantic v2 migration and several other design changes, it was heavily refactored since then.

[Notional]: https://github.com/jheddings/notional
[notion-sdk-py]: https://github.com/ramnes/notion-sdk-py/
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx
import notion_client

from ultimate_notion.config import get_cfg_file
from ultimate_notion.obj_api.endpoints import NotionAPI

if TYPE_CHECKING:
    from ultimate_notion.config import Config


_logger = logging.getLogger(__name__)


def create_notion_client(cfg: Config, **kwargs: Any) -> notion_client.Client:
    """Create a Notion client with the given authentication token."""

    class LoggingClient(httpx.Client):
        """A client that logs the request and response."""

        def send(self, request: httpx.Request, **kwargs: Any) -> httpx.Response:
            msg = f'Request: {request.method} {request.url}'
            if request.content:
                msg += f'\n{request.content.decode("utf-8") if isinstance(request.content, bytes) else request.content}'
            _logger.debug(msg)

            response = super().send(request, **kwargs)

            msg = f'Response: {response.status_code} {request.url}'
            response.read()  # Ensure that the response content is fully loaded. Memory schouldn't be an issue here.
            if response.content:
                msg += (
                    f'\n{response.content.decode("utf-8") if isinstance(response.content, bytes) else response.content}'
                )
            _logger.debug(msg)

            return response

    if (auth := cfg.ultimate_notion.token) is None:
        msg = f'No Notion token found! Check {get_cfg_file()}.'
        raise RuntimeError(msg)

    # Same sane default as notion_client defines its own logger
    kwargs.setdefault('logger', logging.getLogger('notion_client'))
    kwargs.setdefault('log_level', logging.NOTSET)
    return notion_client.Client(auth=auth, client=LoggingClient(), **kwargs)


__all__ = ['NotionAPI', 'create_notion_client']

# ToDo: Recheck every model if `= None` really is needed. Maybe come up with an even smarter way
#       to differentiate between a model for sending and receiving data.
#       Idea: Use a sentinel value, e.g. API_RESPONSE = object() as default value for fields that are only given
#       by the API and not sent to the API. This way we can differentiate between the two cases.

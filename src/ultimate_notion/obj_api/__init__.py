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
import platform
from importlib.metadata import version
from typing import TYPE_CHECKING, Any

import httpx
import notion_client

from ultimate_notion import __version__
from ultimate_notion.config import get_cfg_file
from ultimate_notion.obj_api.endpoints import NotionAPI

if TYPE_CHECKING:
    from ultimate_notion.config import Config


_logger = logging.getLogger(__name__)


def _get_default_user_agent() -> str:
    """Return the default user agent string for the Notion client."""
    python_version = platform.python_version()
    os_name = platform.system()
    architecture = platform.machine()
    httpx_version = httpx.__version__
    notion_sdk_version = version('notion-client')
    return ' '.join(
        f'ultimate-notion/{__version__} (https://ultimate-notion.com/)'
        f'python/{python_version}'
        f'{os_name}/{architecture}'
        f'notion-sdk-py/{notion_sdk_version}'
        f'httpx/{httpx_version}'
    )


def create_notion_client(cfg: Config, **kwargs: Any) -> notion_client.Client:
    """Create a Notion client with the given authentication token."""
    if (auth := cfg.ultimate_notion.token) is None:
        msg = f'No Notion token found! Check {get_cfg_file()}.'
        raise RuntimeError(msg)

    # Set same sane defaults as notion_client defines its own logger
    kwargs.setdefault('logger', logging.getLogger('notion_client'))
    kwargs.setdefault('log_level', logging.NOTSET)

    def log_request(request: httpx.Request) -> None:
        msg = f'Request: {request.method} {request.url}'
        try:
            if request.content:
                msg += f'\n{request.content.decode("utf-8") if isinstance(request.content, bytes) else request.content}'
        except httpx.RequestNotRead:
            # For streaming requests (like file uploads), we can't access content without reading it first
            msg += '\n<streaming content>'
        _logger.debug(msg)

    def log_response(response: httpx.Response) -> None:
        msg = f'Response: {response.status_code} {response.url}'
        response.read()  # Ensure that the response content is fully loaded. Memory schouldn't be an issue here.
        if response.content:
            msg += f'\n{response.content.decode("utf-8") if isinstance(response.content, bytes) else response.content}'
        _logger.debug(msg)

    user_agent = kwargs.pop('user_agent', _get_default_user_agent())
    httpx_client = httpx.Client(event_hooks={'request': [log_request], 'response': [log_response]})
    client = notion_client.Client(auth=auth, client=httpx_client, **kwargs)
    # we need to set the user agent manually, because notion_client ovewrites it during initialization
    httpx_client.headers['User-Agent'] = user_agent
    return client


__all__ = ['NotionAPI', 'create_notion_client']

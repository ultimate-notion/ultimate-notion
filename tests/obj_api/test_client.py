from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import notion_client
import pytest

from ultimate_notion.config import Config, UNOCfg
from ultimate_notion.obj_api import create_notion_client


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable the live Notion cleanup fixture for these isolated client tests."""


def _test_config() -> Config:
    return Config(ultimate_notion=UNOCfg(token='secret', cfg_path=Path(__file__)))


def test_create_notion_client_configures_sdk_retry() -> None:
    with patch.object(notion_client, 'Client', autospec=True) as sdk_client:
        create_notion_client(_test_config())

    retry = sdk_client.call_args.kwargs['retry']
    assert retry == notion_client.RetryOptions(
        max_retries=2,
        initial_retry_delay_ms=1000,
        max_retry_delay_ms=60000,
    )
    sdk_client.call_args.kwargs['client'].close()


def test_create_notion_client_preserves_retry_override() -> None:
    retry = notion_client.RetryOptions(max_retries=4, initial_retry_delay_ms=10, max_retry_delay_ms=100)
    with patch.object(notion_client, 'Client', autospec=True) as sdk_client:
        create_notion_client(_test_config(), retry=retry)

    assert sdk_client.call_args.kwargs['retry'] is retry
    sdk_client.call_args.kwargs['client'].close()


def test_notion_client_retries_rate_limit_response() -> None:
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429,
                headers={'Retry-After': '0'},
                json={
                    'object': 'error',
                    'status': 429,
                    'code': 'rate_limited',
                    'message': 'slow down',
                    'request_id': 'request-id',
                },
            )
        return httpx.Response(200, json={'ok': True})

    client = create_notion_client(_test_config())
    client.client = httpx.Client(transport=httpx.MockTransport(handle_request))
    try:
        response = client.request(path='users/me', method='GET')
    finally:
        client.close()

    assert response == {'ok': True}
    assert len(requests) == 2

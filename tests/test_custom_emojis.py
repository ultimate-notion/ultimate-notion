"""Tests for listing the workspace's custom emojis."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import httpx
import pytest
from notion_client import Client

from tests.conftest import normalize_response
from ultimate_notion import CustomEmoji, Session


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Skip workspace cleanup for tests using a mock transport."""


def test_list_custom_emojis_follows_cursor() -> None:
    cursor = 'opaque:emoji+cursor/='
    requests: list[httpx.Request] = []
    emoji_ids = ['9ac3e083-fa26-44a7-9337-2eefbf312dec', '9350e98a-206b-4ff1-a574-2ac5df9c4036']

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        index = len(requests) - 1
        return httpx.Response(
            200,
            json={
                'object': 'list',
                'type': 'custom_emoji',
                'results': [
                    {'id': emoji_ids[index], 'name': f'emoji_{index}', 'url': f'https://example.com/{index}.png'}
                ],
                'has_more': index == 0,
                'next_cursor': cursor if index == 0 else None,
            },
        )

    client = Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(handle)))
    with Session(client=client) as notion:
        emojis = notion.list_custom_emojis()

    assert [(request.method, request.url.path) for request in requests] == [('GET', '/v1/custom_emojis')] * 2
    assert [dict(request.url.params) for request in requests] == [{}, {'start_cursor': cursor}]
    assert all(isinstance(emoji, CustomEmoji) for emoji in emojis)
    assert [emoji.id for emoji in emojis] == [UUID(value) for value in emoji_ids]
    assert [emoji.name for emoji in emojis] == ['emoji_0', 'emoji_1']
    assert [emoji.url for emoji in emojis] == ['https://example.com/0.png', 'https://example.com/1.png']


def test_list_custom_emojis_with_no_match() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.params['name'] == 'missing_emoji'
        return httpx.Response(
            200, json={'object': 'list', 'type': 'custom_emoji', 'results': [], 'has_more': False, 'next_cursor': None}
        )

    client = Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(handle)))
    with Session(client=client) as notion:
        assert notion.list_custom_emojis(name='missing_emoji') == []


def _redact_emoji_urls(response: dict[str, Any]) -> dict[str, Any]:
    response = normalize_response(response)
    payload = json.loads(response['body']['string'])
    for index, emoji in enumerate(payload.get('results', [])):
        emoji['url'] = f'https://example.com/custom-emoji/{index}.png'
    response['body']['string'] = json.dumps(payload).encode()
    response['headers'] = {key: value for key, value in response['headers'].items() if key.lower() != 'content-length'}
    return response


@pytest.mark.vcr(before_record_response=_redact_emoji_urls, decode_compressed_response=True)
def test_list_workspace_custom_emojis() -> None:
    with Session() as notion:
        emojis = notion.list_custom_emojis()
    assert emojis
    assert all(emoji.name and emoji.url.startswith('https://') for emoji in emojis)

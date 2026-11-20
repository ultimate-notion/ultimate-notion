"""Tests for reading a saved block through Notion's Markdown endpoint."""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from notion_client import Client

from ultimate_notion import Paragraph, Session


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Skip the shared session for this test's mocked Notion client."""


def test_get_markdown_uses_native_endpoint() -> None:
    block_id = UUID('41d9ce7b-60a4-8149-8c9c-f72b8b91ea25')
    paragraph = Paragraph('Cached text')
    paragraph.obj_ref.id = block_id

    def retrieve(request: httpx.Request) -> httpx.Response:
        assert request.method == 'GET'
        assert request.url.path == f'/v1/pages/{block_id}/markdown'
        return httpx.Response(
            200,
            json={
                'object': 'page_markdown',
                'id': str(block_id),
                'markdown': 'Server text',
                'truncated': False,
                'unknown_block_ids': [],
            },
        )

    client = Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(retrieve)))
    with Session(client=client):
        result = paragraph.get_markdown()

    assert result.id == block_id
    assert result.markdown == 'Server text'
    assert result.truncated is False
    assert result.unknown_block_ids == []

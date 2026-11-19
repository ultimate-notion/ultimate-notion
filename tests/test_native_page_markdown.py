"""Round-trip tests for the native page Markdown endpoints."""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from notion_client import Client

from tests.conftest import TESTS_PAGE
from ultimate_notion import Paragraph, Session


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Use the test's own cleanup for its temporary page."""


def test_saved_block_uses_native_markdown() -> None:
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
        assert paragraph.to_markdown() == 'Server text'


@pytest.mark.vcr(decode_compressed_response=True)
def test_native_page_markdown_round_trip() -> None:
    with Session() as notion:
        root = notion.search_page(TESTS_PAGE, exact=True).item()
        page = notion.create_page(parent=root, title='Native Markdown test', blocks=[Paragraph('Old content')])
        try:
            assert page.to_markdown() == 'Old content'
            assert len(page.children) == 1

            response = page.set_markdown('## New heading\n\nNew content')
            assert response.id == page.id
            assert not response.truncated
            assert response.unknown_block_ids == []
            assert '## New heading' in response.markdown
            assert 'Old content' not in response.markdown
            assert page.get_markdown().markdown == response.markdown
            assert len(page.children) == 2
        finally:
            page.delete()

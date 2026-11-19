"""Round-trip tests for the native page Markdown endpoints."""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from notion_client import Client

from tests.conftest import TESTS_PAGE
from ultimate_notion import Page, Paragraph, Session
from ultimate_notion.obj_api.blocks import Page as PageObject


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Use the test's own cleanup for its temporary page."""


def test_get_markdown_preserves_truncation_metadata() -> None:
    page_id = UUID('41d9ce7b-60a4-8149-8c9c-f72b8b91ea25')
    block_id = UUID('41d9ce7b-60a4-8149-8c9c-f72b8b91ea26')
    markdown = f'Visible content\n\n<unknown url="https://www.notion.so/{page_id.hex}#{block_id.hex}" />'

    def retrieve(request: httpx.Request) -> httpx.Response:
        assert request.method == 'GET'
        assert request.url.path == f'/v1/pages/{page_id}/markdown'
        return httpx.Response(
            200,
            json={
                'object': 'page_markdown',
                'id': str(page_id),
                'markdown': markdown,
                'truncated': True,
                'unknown_block_ids': [str(block_id)],
            },
        )

    client = Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(retrieve)))
    with Session(client=client):
        page = Page.wrap_obj_ref(
            PageObject.model_validate({'id': page_id, 'parent': {'type': 'workspace', 'workspace': True}})
        )
        response = page.get_markdown()

    assert response.markdown == markdown
    assert response.truncated is True
    assert response.unknown_block_ids == [block_id]


@pytest.mark.vcr(decode_compressed_response=True)
def test_native_page_markdown_round_trip() -> None:
    with Session() as notion:
        root = notion.search_page(TESTS_PAGE, exact=True).item()
        page = notion.create_page(parent=root, title='Native Markdown test', blocks=[Paragraph('Old content')])
        try:
            assert 'Old content' in page.get_markdown().markdown
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

"""Round-trip tests for the native page Markdown endpoints."""

from __future__ import annotations

import pytest

from tests.conftest import TESTS_PAGE
from ultimate_notion import Paragraph, Session


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Use the test's own cleanup for its temporary page."""


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

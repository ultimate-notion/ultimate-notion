"""Round-trip tests for the native page Markdown endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests.conftest import TESTS_PAGE
from ultimate_notion import Paragraph, Session
from ultimate_notion.cli import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Use the test's own cleanup for its temporary page."""


@pytest.mark.vcr(decode_compressed_response=True)
def test_native_page_markdown_round_trip(tmp_path: Path) -> None:
    with Session() as notion:
        root = notion.search_page(TESTS_PAGE, exact=True).item()
        page = notion.create_page(parent=root, title='Native Markdown test', blocks=[Paragraph('Old content')])
        try:
            output = tmp_path / 'page.md'
            with patch('ultimate_notion.cli.Session') as session_class:
                session_class.return_value.__enter__.return_value = notion
                result = CliRunner().invoke(app, ['export-markdown', str(page.id), str(output)])
            assert result.exit_code == 0, result.output
            assert 'Old content' in output.read_text(encoding='utf-8')
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

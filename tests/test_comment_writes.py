"""Round-trip tests for writing Notion comments."""

from __future__ import annotations

import pytest

from tests.conftest import TESTS_PAGE
from ultimate_notion import Session


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Use the test's own cleanup for its temporary page."""


@pytest.mark.vcr(decode_compressed_response=True)
def test_write_markdown_comment() -> None:
    with Session() as notion:
        root = notion.search_page(TESTS_PAGE, exact=True).item()
        page = notion.create_page(parent=root, title='Comment write test')
        try:
            discussion = page.comments.append(markdown='**A new comment**')
            comment = discussion[-1]
            assert comment.text is not None and comment.text.to_markdown() == '**A new comment**'

            assert comment.update(markdown='*An edited comment*') is comment
            assert comment.text is not None and comment.text.to_markdown() == '*An edited comment*'
            assert [entry.discussion_id for entry in notion.api.comments.list(page.obj_ref)] == [comment.discussion_id]

            discussion.remove(comment)
            assert list(discussion) == []
            assert list(notion.api.comments.list(page.obj_ref)) == []
        finally:
            page.delete()

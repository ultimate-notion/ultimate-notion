from __future__ import annotations

import pytest

from tests.conftest import WIKI_DB
from ultimate_notion.blocks import ChildDatabase, ChildPage
from ultimate_notion.obj_api.blocks import ChildDatabase as ChildDatabaseObject
from ultimate_notion.page import Page
from ultimate_notion.session import Session


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Use the test's own cleanup for the temporary wiki page."""


@pytest.mark.vcr()
def test_wiki_child_block_parent_and_ancestors(notion: Session, root_page: Page) -> None:
    wiki_block = next(
        ChildDatabase.wrap_obj_ref(block)
        for block in notion.api.blocks.children.list(root_page.id)
        if isinstance(block, ChildDatabaseObject) and block.child_database.title == WIKI_DB
    )
    wiki = notion.get_db(wiki_block.id)
    assert wiki.obj_ref.database_type == 'wiki'

    page = notion.create_page(wiki.data_sources.item(), title='Temporary wiki ancestry test')
    try:
        assert page.parent is wiki
        assert page.ancestors == (root_page, wiki)

        child = notion.get_block(page.id, use_cache=False)
        assert isinstance(child, ChildPage)
        assert child.parent is wiki
        assert child.ancestors == (root_page, wiki)
    finally:
        assert page.delete().is_deleted

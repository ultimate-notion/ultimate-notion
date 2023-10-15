from __future__ import annotations

from ultimate_notion.page import Page


def test_parent(page_hierarchy):
    root_page, l1_page, l2_page = page_hierarchy
    assert isinstance(root_page, Page)
    assert isinstance(l1_page, Page)
    assert isinstance(l2_page, Page)

    assert root_page.parent is None
    assert l2_page.parent == l1_page
    assert l1_page.parent == root_page
    assert l2_page.parent.parent == root_page


def test_parents(page_hierarchy):
    root_page, l1_page, l2_page = page_hierarchy
    assert l2_page.parents == (root_page, l1_page)

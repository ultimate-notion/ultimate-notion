from __future__ import annotations

from ultimate_notion import Page, Session


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


def test_delete_restore_page(notion: Session, root_page: Page):
    page = notion.create_page(root_page)
    assert not page.is_archived
    page.delete()
    assert page.is_archived
    page.restore()
    assert not page.is_archived


def test_reload_page(notion: Session, root_page: Page):
    page = notion.create_page(root_page)
    old_obj_id = id(page.obj_ref)
    page.reload()
    assert old_obj_id != id(page.obj_ref)

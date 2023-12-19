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


def test_ancestors(page_hierarchy: tuple[Page, ...]):
    root_page, l1_page, l2_page = page_hierarchy
    assert l2_page.ancestors == (root_page, l1_page)


def test_delete_restore_page(notion: Session, root_page: Page):
    page = notion.create_page(root_page)
    assert not page.is_deleted
    page.delete()
    assert page.is_deleted
    page.restore()
    assert not page.is_deleted


def test_reload_page(notion: Session, root_page: Page):
    page = notion.create_page(root_page)
    old_obj_id = id(page.obj_ref)
    page.reload()
    assert old_obj_id != id(page.obj_ref)


def test_parent_children(notion: Session, root_page: Page):
    parent = notion.create_page(root_page, title='Parent')
    child1 = notion.create_page(parent, title='Child 1')
    child2 = notion.create_page(parent, title='Child 2')

    assert child1.parent == parent
    assert child2.parent == parent
    assert parent.children == [child1, child2]
    assert all(isinstance(child, Page) for child in parent.children)
    assert child1.ancestors == (root_page, parent)

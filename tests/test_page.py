from __future__ import annotations

import re
from textwrap import dedent

import pytest

from ultimate_notion import Database, Emoji, FileInfo, Page, RichText, Session
from ultimate_notion.blocks import Block


@pytest.mark.vcr()
def test_parent(page_hierarchy):
    root_page, l1_page, l2_page = page_hierarchy
    assert isinstance(root_page, Page)
    assert isinstance(l1_page, Page)
    assert isinstance(l2_page, Page)

    assert root_page.parent is None
    assert l2_page.parent == l1_page
    assert l1_page.parent == root_page
    assert l2_page.parent.parent == root_page


@pytest.mark.vcr()
def test_ancestors(page_hierarchy: tuple[Page, ...]):
    root_page, l1_page, l2_page = page_hierarchy
    assert l2_page.ancestors == (root_page, l1_page)


@pytest.mark.vcr()
def test_delete_restore_page(notion: Session, root_page: Page):
    page = notion.create_page(root_page)
    assert not page.is_deleted
    page.delete()
    assert page.is_deleted
    page.restore()
    assert not page.is_deleted


@pytest.mark.vcr()
def test_reload_page(notion: Session, root_page: Page):
    page = notion.create_page(root_page)
    old_obj_id = id(page.obj_ref)
    page.reload()
    assert old_obj_id != id(page.obj_ref)


@pytest.mark.vcr()
def test_parent_subpages(notion: Session, root_page: Page):
    parent = notion.create_page(root_page, title='Parent')
    child1 = notion.create_page(parent, title='Child 1')
    child2 = notion.create_page(parent, title='Child 2')

    assert child1.parent == parent
    assert child2.parent == parent
    assert parent.subpages == [child1, child2]
    assert all(isinstance(page, Page) for page in parent.subpages)
    assert child1.ancestors == (root_page, parent)


@pytest.mark.vcr()
def test_parent_children(intro_page: Page):
    assert all(isinstance(block, Block) for block in intro_page.children)


@pytest.mark.vcr()
def test_parent_subdbs(notion: Session, root_page: Page):
    parent = notion.create_page(root_page, title='Parent')
    db1 = notion.create_db(parent)
    db2 = notion.create_db(parent)

    assert db1.parent == parent
    assert db2.parent == parent
    assert parent.subdbs == [db1, db2]
    assert all(isinstance(db, Database) for db in parent.subdbs)
    assert db1.ancestors == (root_page, parent)


@pytest.mark.vcr()
def test_icon_attr(notion: Session, root_page: Page):
    new_page = notion.create_page(parent=root_page, title='My new page with icon')

    assert new_page.icon is None
    emoji_icon = '🐍'
    new_page.icon = emoji_icon  # type: ignore[assignment] # test automatic conversation
    assert isinstance(new_page.icon, Emoji)
    assert new_page.icon == emoji_icon

    new_page.icon = Emoji(emoji_icon)
    assert isinstance(new_page.icon, Emoji)
    assert new_page.icon == emoji_icon

    # clear cache and retrieve the database again to be sure it was udpated on the server side
    del notion.cache[new_page.id]
    new_page = notion.get_page(new_page.id)
    assert new_page.icon == Emoji(emoji_icon)

    notion_icon = 'https://www.notion.so/icons/snake_purple.svg'
    new_page.icon = notion_icon  # test automatic conversation
    assert isinstance(new_page.icon, FileInfo)
    assert new_page.icon == notion_icon

    new_page.icon = FileInfo(url=notion_icon)
    assert isinstance(new_page.icon, FileInfo)
    assert new_page.icon == notion_icon

    new_page.reload()
    assert new_page.icon == FileInfo(url=notion_icon)

    new_page.icon = None
    new_page.reload()
    assert new_page.icon is None


@pytest.mark.vcr()
def test_cover_attr(notion: Session, root_page: Page):
    new_page = notion.create_page(parent=root_page, title='My new page with cover')

    assert new_page.cover is None
    cover_file = 'https://www.notion.so/images/page-cover/woodcuts_2.jpg'
    new_page.cover = cover_file  # type: ignore[assignment] # test automatic conversation
    assert isinstance(new_page.cover, FileInfo)
    assert new_page.cover == cover_file

    new_page.cover = FileInfo(url=cover_file)
    assert isinstance(new_page.cover, FileInfo)
    assert new_page.cover == cover_file

    new_page.reload()
    assert new_page.cover == FileInfo(url=cover_file)

    new_page.cover = None
    new_page.reload()
    assert new_page.cover is None


@pytest.mark.vcr()
def test_title_attr(notion: Session, root_page: Page):
    new_page = notion.create_page(parent=root_page)

    assert new_page.title == ''

    title = 'My new title'
    new_page.title = title  # type: ignore[assignment] # test automatic conversation
    assert isinstance(new_page.title, RichText)
    assert new_page.title == title

    new_page.title = RichText(title)
    assert isinstance(new_page.title, RichText)
    assert new_page.title == title

    new_page.reload()
    assert new_page.title == RichText(title)

    new_page.title = None  # type: ignore[assignment]
    new_page.reload()
    assert new_page.title == ''

    new_page.title = ''  # type: ignore[assignment]
    new_page.reload()
    assert new_page.title == ''


@pytest.mark.vcr()
def test_created_edited_by(notion: Session, root_page: Page):
    myself = notion.whoami()
    florian = notion.search_user('Florian Wilhelm').item()
    assert root_page.created_by == florian
    assert root_page.last_edited_by in {myself, florian}


@pytest.mark.vcr()
def test_page_to_markdown(md_page: Page):
    exp_output = dedent(
        """
        # Headline 1
        ## Headline 2
        ### Headline 3
        ---

        # Toggle Headline 1
        ## Toggle Headline 2
        ### Toggle Headline 3
        - Item 1

        - Item 2
        with a new line

        - Item 3

        - [ ] ToDo1

        - [ ] ToDo2
        with a new line

        - [x] Checked ToDo3

        1. First item

        1. Second item
        with a new line

        1. Third item

        > This is a quote
        with a new line

        💡 Callout!

        |           |           |
        |-----------|-----------|
        | Cell 1, 1 | Cell 1, 2 |
        | Cell 2, 1 | Cell 2, 2 |
        | Cell 3, 1 | Cell 3, 2 |

        # This is an emoji! 😀😀
        $$
        |x|=\\begin{cases}x, &\\quad x \\geq 0\\\\-x, &\\quad x < 0\\end{cases}
        $$

        ```python
        # Python Code
        import ultimate_notion
        ```
        [https://picsum.photos/300/300](https://picsum.photos/300/300)

        ![1004-300x300.jpg](https://)

        [📎 logo_with_text.svg](https://ultimate-notion.com/latest/assets/images/logo_with_text.svg)

        ## Unsupported Stuff in Markdown
        <!--- column 1 -->
        # Column 1
        <!--- column 2 -->
        # Column
        ```{toc}
        ```
        Tests / Markdown Page Test

        [📄 **<u>Markdown SubPage Test</u>**](https://notion.so/67ad5240b1b944679b073ef3ebbbc755)

        <!--- original block -->
        # This is the original Paragraph on Page
        <!--- synched block -->
        # This is the original Paragraph on SubPage
        [**↗️ <u>Markdown SubPage Test</u>**](https://notion.so/67ad5240b1b944679b073ef3ebbbc755)

        <kbd>Unsupported block</kbd>
    """
    )
    markdown = md_page.to_markdown().strip().split('\n')
    img_line = markdown[51]
    img_line = re.sub(r'\?.*?\]', ']', img_line)
    img_line = re.sub(r'prod.*?\)', ')', img_line)
    markdown[51] = img_line

    for exp, act in zip(exp_output.strip().split('\n'), markdown, strict=True):
        assert exp == act

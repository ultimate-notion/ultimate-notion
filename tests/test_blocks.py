from __future__ import annotations

from textwrap import dedent
from typing import cast

import pytest

import ultimate_notion as uno
from ultimate_notion import Session
from ultimate_notion.blocks import ChildDatabase, ChildPage
from ultimate_notion.page import Page


@pytest.mark.vcr()
def test_append_blocks(root_page: Page, notion: Session):
    page = notion.create_page(parent=root_page, title='Page for appending blocks')
    h1 = uno.Heading1('My new page')
    page.append(h1)

    assert len(page.children) == 1
    assert page.children[0] == h1

    page.reload()
    assert len(page.children) == 1
    assert page.children[0] == h1

    h2 = uno.Heading2('Heading 2')
    h3 = uno.Heading2('Heading 3')
    h4 = uno.Heading2('Heading 4')
    h21 = uno.Heading3('Heading 2.1', toggleable=True, color=uno.Color.RED)
    page.append([h2, h3, h4])
    page.append(h21, after=h2)

    assert page.children == [h1, h2, h21, h3, h4]


@pytest.mark.vcr()
def test_delete_blocks(root_page: Page, notion: Session):
    page = notion.create_page(parent=root_page, title='Page for deleting blocks')
    h = uno.Heading1('My new page')
    p = uno.Paragraph('This is a paragraph')
    page.append([h, p])
    assert page.children == [h, p]
    assert not h.is_deleted
    assert not p.is_deleted

    p.delete()
    assert page.children == [h]
    assert p.is_deleted

    h.delete()
    assert h.is_deleted
    page.reload()
    assert page.children == []


@pytest.mark.vcr()
def test_create_basic_blocks(root_page: Page, notion: Session):
    page = notion.create_page(parent=root_page, title='Page for creating basic blocks')
    children: list[uno.AnyBlock] = [
        uno.Heading1('My new page'),
        uno.Heading2('Heading 2', color=uno.Color.BLUE),
        uno.Paragraph('This is a paragraph'),
        uno.Paragraph('This is coloured paragraph', color=uno.Color.RED),
        uno.Code('print("Hello World")', language=uno.CodeLang.PYTHON),
        uno.Code('SELECT * FROM table', language=uno.CodeLang.SQL, caption='SQL Query'),
        uno.Quote('This is a quote'),
        uno.Quote('This is a quote with a citation', color=uno.Color.GREEN),
        uno.Callout('This is a callout'),
        uno.Callout('This is a callout with color and icon', color=uno.Color.PURPLE, icon='🚀'),
        uno.Callout('This is a another callout with color and icon', color=uno.Color.YELLOW, icon=':thumbs_up:'),
        uno.BulletedItem('First item'),
        uno.BulletedItem('Second item', color=uno.Color.BLUE),
        uno.NumberedItem('First item'),
        uno.NumberedItem('Second item', color=uno.Color.RED),
        uno.ToDoItem('First item'),
        uno.ToDoItem('Second item', checked=True),
        uno.ToDoItem('Third item', checked=False, color=uno.Color.RED),
        uno.ToggleItem('First item'),
        uno.ToggleItem('Second item', color=uno.Color.PURPLE),
        uno.Divider(),
        uno.TableOfContents(),
        uno.TableOfContents(color=uno.Color.PINK),
        uno.Breadcrumb(),
        uno.Embed('https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
        uno.Embed('https://www.youtube.com/watch?v=dQw4w9WgXcQ', caption='Rick Roll'),
        uno.Bookmark('https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
        uno.Bookmark('https://www.youtube.com/watch?v=dQw4w9WgXcQ', caption='Rick Roll'),
        uno.Equation(r'-1 = \exp(i \pi)'),
    ]
    page.append(children)
    output = page.to_markdown()
    exp_output = dedent("""
        # My new page
        ## Heading 2
        This is a paragraph
        This is coloured paragraph
        ```python
        print("Hello World")
        ```
        ```sql
        SELECT * FROM table
        ```
        > This is a quote

        > This is a quote with a citation

        💡 This is a callout

        🚀 This is a callout with color and icon

        👍 This is a another callout with color and icon

        - First item

        - Second item

        1. First item

        1. Second item

        - [ ] First item

        - [x] Second item

        - [ ] Third item

        - First item

        - Second item

        ---

        ```{toc}
        ```
        ```{toc}
        ```
        Tests / Page for creating basic blocks

        [https://www.youtube.com/watch?v=dQw4w9WgXcQ](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

        [https://www.youtube.com/watch?v=dQw4w9WgXcQ](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

        Bookmark: [https://www.youtube.com/watch?v=dQw4w9WgXcQ](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

        Bookmark: [https://www.youtube.com/watch?v=dQw4w9WgXcQ](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

        $$
        -1 = \\exp(i \\pi)
        $$
    """)
    for exp, act in zip(exp_output.lstrip('\n').split('\n'), output.split('\n'), strict=True):
        assert exp == act

    # test appending to an actual block
    paragraph_with_children = uno.Paragraph('This is a paragraph with children')
    with pytest.raises(RuntimeError):
        paragraph_with_children.append(uno.Paragraph('This is a child paragraph'))

    page.append(paragraph_with_children)
    paragraph_with_children.append(uno.Paragraph('This is a child paragraph'))

    assert len(paragraph_with_children.children) == 1


@pytest.mark.vcr()
def test_create_file_blocks(root_page: Page, notion: Session):
    page = notion.create_page(parent=root_page, title='Page for creating file blocks')
    children: list[uno.AnyBlock] = [
        uno.File('robots.txt', 'https://www.google.de/robots.txt'),
        uno.File('robots.txt', 'https://www.google.de/robots.txt', caption='Google Robots'),
        uno.Image('https://cdn.pixabay.com/photo/2019/08/06/09/16/flowers-4387827_1280.jpg'),
        uno.Image('https://cdn.pixabay.com/photo/2019/08/06/09/16/flowers-4387827_1280.jpg', caption='Path on meadow'),
        uno.Video('https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
        uno.Video('https://www.youtube.com/watch?v=dQw4w9WgXcQ', caption='Rick Roll'),
        uno.PDF('https://www.iktz-hd.de/fileadmin/user_upload/dummy.pdf'),
        uno.PDF('https://www.iktz-hd.de/fileadmin/user_upload/dummy.pdf', caption='Dummy PDF'),
    ]
    page.append(children)
    output = page.to_markdown()
    exp_output = dedent("""
        [📎 robots.txt](https://www.google.de/robots.txt)

        [📎 robots.txt](https://www.google.de/robots.txt)
        Google Robots

        ![flowers-4387827_1280.jpg](https://cdn.pixabay.com/photo/2019/08/06/09/16/flowers-4387827_1280.jpg)

        <figure><img src="https://cdn.pixabay.com/photo/2019/08/06/09/16/flowers-4387827_1280.jpg" alt="flowers-4387827_1280.jpg" /><figcaption>Path on meadow</figcaption></figure>

        <video width="320" height="240" controls><source src="https://www.youtube.com/watch?v=dQw4w9WgXcQ"></video>

        <video width="320" height="240" controls><source src="https://www.youtube.com/watch?v=dQw4w9WgXcQ"></video>

        [📖 dummy.pdf](https://www.iktz-hd.de/fileadmin/user_upload/dummy.pdf)

        [📖 dummy.pdf](https://www.iktz-hd.de/fileadmin/user_upload/dummy.pdf)
        Dummy PDF
    """)  # noqa: E501
    for exp, act in zip(exp_output.lstrip('\n').split('\n'), output.split('\n'), strict=True):
        assert exp == act


@pytest.mark.vcr()
def test_create_child_blocks(root_page: Page, notion: Session):
    page = notion.create_page(parent=root_page, title='Page for creating child blocks')
    subpage = notion.create_page(parent=page, title='Subpage')
    subdb = notion.create_db(parent=page)
    assert page.children == [subpage, subdb]  # This works as we only compare the IDs
    page.reload()
    assert page.children == [subpage, subdb]
    child_page, child_db = page.children
    assert cast(ChildPage, child_page).page == subpage
    assert cast(ChildDatabase, child_db).db == subdb

    for child in page.children:
        child.delete()

    assert page.children == []
    page.reload()
    assert page.children == []


@pytest.mark.vcr()
def test_create_column_blocks(root_page: Page, notion: Session):
    page = notion.create_page(parent=root_page, title='Page for creating column blocks')
    cols = uno.Columns(2)
    page.append(cols)
    cols[0].append(uno.Paragraph('Column 1'))
    cols[1].append(uno.Paragraph('Column 2'))
    output = page.to_markdown()
    exp_output = dedent("""
        <!--- column 1 -->
        Column 1
        <!--- column 2 -->
        Column 2
    """)
    for exp, act in zip(exp_output.strip('\n').split('\n'), output.split('\n'), strict=True):
        assert exp == act


@pytest.mark.vcr()
def test_create_table_blocks(root_page: Page, notion: Session):
    page = notion.create_page(parent=root_page, title='Page for creating table blocks')
    table = uno.Table(2, 2)
    page.append(table)
    # ToDo: When modifying is implemented, add more tests
    # table[0, 0] = uno.Paragraph('Cell 1')
    # table[0, 1] = uno.Paragraph('Cell 2')
    # table[1, 0] = uno.Paragraph('Cell 3')
    # table[1, 1] = uno.Paragraph('Cell 4')
    output = page.to_markdown()
    exp_output = dedent("""
        |    |    |
        |----|----|
        |    |    |
        |    |    |
    """)
    for exp, act in zip(exp_output.lstrip('\n').split('\n'), output.split('\n'), strict=True):
        assert exp == act


@pytest.mark.vcr()
def test_create_link_blocks(root_page: Page, notion: Session):
    page = notion.create_page(parent=root_page, title='Page for creating link blocks')
    target_page = notion.create_page(parent=root_page, title='Target Page')
    link = uno.LinkToPage(target_page)
    page.append(link)
    output = page.to_markdown()
    exp_output = '[**↗️ <u>Target Page</u>**]('
    assert output.startswith(exp_output)


@pytest.mark.vcr()
def test_create_sync_blocks(root_page: Page, notion: Session):
    page = notion.create_page(parent=root_page, title='Page for creating sync blocks')
    orig_block = uno.SyncedBlock(uno.Paragraph('This is a synced paragraph'))
    with pytest.raises(RuntimeError):
        sync_block = orig_block.create_synced()

    page.append(orig_block)
    sync_block = orig_block.create_synced()
    page.append(sync_block)

    output = page.to_markdown()
    exp_output = dedent("""
        <!--- original block -->
        This is a synced paragraph
        <!--- synced block -->
        This is a synced paragraph
    """)
    for exp, act in zip(exp_output.strip('\n').split('\n'), output.split('\n'), strict=True):
        assert exp == act

    with pytest.raises(RuntimeError):
        sync_block = sync_block.create_synced()

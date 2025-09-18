from __future__ import annotations

from textwrap import dedent
from typing import cast

import pytest

import ultimate_notion as uno
from ultimate_notion import blocks as uno_blocks
from ultimate_notion.blocks import ChildrenMixin
from ultimate_notion.errors import InvalidAPIUsageError, UnsetError
from ultimate_notion.obj_api.core import Unset


@pytest.mark.vcr()
def test_append_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for appending blocks')
    h1 = uno.Heading1('My new page')
    page.append(h1)

    # We guarantee that the objects stay the same
    assert h1 is page.children[0]
    assert page.children[0].parent is page

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

    added_children = (h1, h2, h21, h3, h4)
    assert page.children == added_children
    assert all(pchild is achild for pchild, achild in zip(page.children, added_children, strict=True))


@pytest.mark.vcr()
def test_delete_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for deleting blocks')
    h = uno.Heading1('My new page')
    p = uno.Paragraph('This is a paragraph')
    page.append([h, p])
    assert page.children == (h, p)
    assert not h.is_deleted
    assert not p.is_deleted

    p.delete()
    assert page.children == (h,)
    assert p.is_deleted

    h.delete()
    assert h.is_deleted
    page.reload()
    assert page.children == ()


@pytest.mark.vcr()
def test_create_basic_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for creating basic blocks')
    children: list[uno.Block] = [
        uno.Heading1('My new page'),
        uno.Heading2('Heading 2', color=uno.Color.BLUE),
        uno.Paragraph('This is a paragraph'),
        uno.Paragraph('This is coloured paragraph', color=uno.Color.RED),
        uno.Code('print("Hello World")', language=uno.CodeLang.PYTHON),
        uno.Code('SELECT * FROM table', language=uno.CodeLang.SQL, caption='SQL Query'),
        uno.Quote('This is a quote'),
        uno.Quote('This is a quote with a citation', color=uno.Color.GREEN),
        uno.Callout('This is a callout'),
        uno.Callout('This is a callout with color and icon', color=uno.Color.PURPLE, icon=uno.Emoji('🚀')),
        uno.Callout(
            'This is a another callout with color and icon', color=uno.Color.YELLOW, icon=uno.Emoji(':thumbs_up:')
        ),
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
        # Page for creating basic blocks

        ## My new page
        ### Heading 2
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

        [Rick Roll](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

        Bookmark: [https://www.youtube.com/watch?v=dQw4w9WgXcQ](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

        Bookmark: [Rick Roll](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

        $$
        -1 = \\exp(i \\pi)
        $$
    """)
    for exp, act in zip(exp_output.lstrip('\n').split('\n'), output.split('\n'), strict=True):
        assert exp == act

    # test appending to an actual block
    paragraph_with_children = uno.Paragraph('This is a paragraph with children')
    with pytest.raises(InvalidAPIUsageError):
        paragraph_with_children.append(uno.Paragraph('This is a child paragraph'), sync=True)

    page.append(paragraph_with_children)
    paragraph_with_children.append(uno.Paragraph('This is a child paragraph'))

    assert len(paragraph_with_children.children) == 1


@pytest.mark.vcr()
def test_create_file_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for creating file blocks')
    children: list[uno.Block] = [
        uno.File(uno.url('https://www.google.de/robots.txt'), name='robots.txt'),
        uno.File(uno.url('https://www.google.de/robots.txt', name='robots.txt'), caption='Google Robots'),
        uno.Image(uno.url('https://cdn.pixabay.com/photo/2019/08/06/09/16/flowers-4387827_1280.jpg')),
        uno.Image(
            uno.url('https://cdn.pixabay.com/photo/2019/08/06/09/16/flowers-4387827_1280.jpg'), caption='Path on meadow'
        ),
        uno.Video(uno.url('https://www.youtube.com/watch?v=dQw4w9WgXcQ')),
        uno.Video(uno.url('https://www.youtube.com/watch?v=dQw4w9WgXcQ'), caption='Rick Roll'),
        uno.PDF(uno.url('https://www.iktz-hd.de/fileadmin/user_upload/dummy.pdf')),
        uno.PDF(uno.url('https://www.iktz-hd.de/fileadmin/user_upload/dummy.pdf'), caption='Dummy PDF'),
    ]
    page.append(children)
    output = page.to_markdown()
    exp_output = dedent("""
        # Page for creating file blocks

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
def test_create_child_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for creating child blocks')
    subpage = notion.create_page(parent=page, title='Subpage')
    subdb = notion.create_db(parent=page)
    assert page.children == (subpage, subdb)  # This works as we only compare the IDs
    page.reload()
    assert page.children == (subpage, subdb)
    child_page, child_db = page.children
    assert child_page is subpage
    assert child_db is subdb

    for child in page.children:
        child.delete()

    assert page.children == ()
    page.reload()
    assert page.children == ()


@pytest.mark.vcr()
def test_create_column_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for creating column blocks')
    cols = uno.Columns(2)
    page.append(cols)
    cols[0].append(uno.Paragraph('Column 1'))
    cols[1].append(uno.Paragraph('Column 2'))
    output = page.to_markdown()
    exp_output = dedent("""
        # Page for creating column blocks

        <!--- column 1 -->
        Column 1
        <!--- column 2 -->
        Column 2
    """)
    for exp, act in zip(exp_output.strip('\n').split('\n'), output.split('\n'), strict=True):
        assert exp == act


@pytest.mark.vcr()
def test_create_table_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for creating table blocks')
    table = uno.Table(3, 2, header_row=True)
    page.append(table)
    table[0] = ('Column 1', 'Column 2')
    table[1, 0] = 'Cell 1,0'
    table[1, 1] = 'Cell 1,1'
    table[2, 0] = 'Cell 2,0'
    table[2, 1] = 'Cell 2,1'
    output = page.to_markdown()
    exp_output = dedent("""
        # Page for creating table blocks

        | Column 1   | Column 2   |
        |------------|------------|
        | Cell 1,0   | Cell 1,1   |
        | Cell 2,0   | Cell 2,1   |
    """)
    for exp, act in zip(exp_output.lstrip('\n').split('\n'), output.split('\n'), strict=True):
        assert exp == act


@pytest.mark.vcr()
def test_create_link_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for creating link blocks')
    target_page = notion.create_page(parent=root_page, title='Target Page')
    link = uno.LinkToPage(target_page)
    page.append(link)
    output = page.children[0].to_markdown()
    exp_output = '[**↗️ <u>Target Page</u>**]('
    assert output.startswith(exp_output)


@pytest.mark.vcr()
def test_create_sync_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for creating sync blocks')
    orig_block = uno.SyncedBlock(uno.Paragraph('This is a synced paragraph'))
    with pytest.raises(RuntimeError):
        sync_block = orig_block.create_synced()

    page.append(orig_block)
    sync_block = orig_block.create_synced()
    page.append(sync_block)

    output = page.to_markdown()
    exp_output = dedent("""
        # Page for creating sync blocks

        <!--- original block -->
        This is a synced paragraph
        <!--- synced block -->
        This is a synced paragraph
    """)
    for exp, act in zip(exp_output.strip('\n').split('\n'), output.split('\n'), strict=True):
        assert exp == act

    with pytest.raises(RuntimeError):
        sync_block = sync_block.create_synced()


@pytest.mark.vcr()
def test_nested_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for creating nested blocks')
    h1 = uno.Heading1('Non-toggleable Heading')
    p1 = uno.Paragraph('This is a paragraph')
    page.append(h1)
    with pytest.raises(InvalidAPIUsageError):
        h1.append(p1)

    h1 = uno.Heading1('Toggleable Heading', toggleable=True)
    page.append(h1)
    h1.append(p1)

    p2 = uno.Paragraph('This is a paragraph with a nested element')
    page.append(p2)
    p2.append(uno.Paragraph('Nested Paragraph'))

    assert len(page.children) == 3
    assert cast(ChildrenMixin, page.children[1]).children == (p1,)
    assert len(cast(ChildrenMixin, page.children[2]).children) == 1


@pytest.mark.vcr()
def test_has_children(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for checking children')
    assert not page.has_children
    page.append(uno.Paragraph('This is a paragraph'))
    assert page.has_children


@pytest.mark.vcr()
def test_modify_basic_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for modifying basic blocks')
    children: list[uno.Block] = [
        paragraph := uno.Paragraph('Red paragraph', color=uno.Color.RED),
        code := uno.Code('print("Hello World")', language=uno.CodeLang.PYTHON),
        heading := uno.Heading1('My new page', toggleable=True),
        callout := uno.Callout('This is a callout', icon=uno.Emoji('🚀')),
        todo := uno.ToDoItem('Checked item', checked=True),
        embed := uno.Embed('https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
        bookmark := uno.Bookmark('https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
        equation := uno.Equation(r'-1 = \exp(i \pi)'),
    ]
    page.append(children)

    paragraph.color = uno.Color.PINK
    paragraph.rich_text = uno.text('Pink paragraph')
    paragraph.reload()
    assert paragraph.color == uno.Color.PINK

    code.language = uno.CodeLang.JAVASCRIPT
    code.caption = uno.text('JavaScript Code')

    heading.append(uno.Paragraph('This is a nested paragraph'))
    with pytest.raises(InvalidAPIUsageError):
        heading.toggleable = False
    heading.children[0].delete()
    heading.toggleable = False

    assert callout.icon == uno.Emoji('🚀')
    callout.icon = uno.Emoji(':thumbs_up:')

    todo.checked = False

    embed.url = 'https://notion.so'
    embed.caption = uno.text('Notion Homepage')

    bookmark.url = 'https://notion.so'

    equation.latex = r'e = mc^2'

    page.reload()

    child_paragraph = cast(uno.Paragraph, page.children[0])
    assert child_paragraph.color == uno.Color.PINK
    assert child_paragraph.rich_text == 'Pink paragraph'

    child_code = cast(uno.Code, page.children[1])
    assert child_code.language == uno.CodeLang.JAVASCRIPT
    assert child_code.caption == uno.text('JavaScript Code')
    child_code.caption = None
    child_code.reload()
    assert child_code.caption is None

    child_heading = cast(uno.Heading1, page.children[2])
    assert child_heading.toggleable is False

    child_callout = cast(uno.Callout, page.children[3])
    assert child_callout.icon == '👍'

    child_todo = cast(uno.ToDoItem, page.children[4])
    assert child_todo.checked is False

    child_embed = cast(uno.Embed, page.children[5])
    assert child_embed.caption == 'Notion Homepage'

    child_bookmark = cast(uno.Bookmark, page.children[6])
    assert child_bookmark.url == 'https://notion.so'

    child_equation = cast(uno.Equation, page.children[7])
    assert child_equation.latex == r'e = mc^2'


@pytest.mark.vcr()
def test_modify_file_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for modifying file blocks')
    children: list[uno.Block] = [
        file := uno.File(
            uno.url(
                'https://www.google.de/robots.txt',
                name='robots.txt',
            )
        ),
        image := uno.Image(
            uno.url('https://cdn.pixabay.com/photo/2019/08/06/09/16/flowers-4387827_1280.jpg'), caption='Path on meadow'
        ),
        video := uno.Video(uno.url('https://www.youtube.com/watch?v=dQw4w9WgXcQ')),
        pdf := uno.PDF(uno.url('https://www.iktz-hd.de/fileadmin/user_upload/dummy.pdf')),
    ]
    page.append(children)

    file.name = 'my_robot'
    assert file.caption is None
    new_caption_text = 'My Robot.txt of Google'
    file.caption = new_caption_text

    file.reload()
    assert file.name == 'my_robot.txt'
    assert file.caption == new_caption_text

    assert image.caption == 'Path on meadow'
    new_caption_text = 'Flowers on meadow'
    image.caption = uno.text(new_caption_text)
    image.reload()
    assert image.caption == new_caption_text

    assert video.caption is None
    new_caption_text = 'Rick Roll but not really'
    video.caption = new_caption_text
    video.reload()
    assert video.caption == uno.text(new_caption_text)

    new_caption_text = 'Dummy PDF'
    pdf.caption = uno.text(new_caption_text)
    pdf.reload()
    assert pdf.caption == new_caption_text


@pytest.mark.vcr()
def test_modify_column_blocks(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for modifying column blocks')
    with pytest.raises(ValueError):
        uno.Columns(1)

    cols = uno.Columns(2)
    page.append(cols)
    assert cols[0].width_ratio is None
    assert cols[1].width_ratio is None

    cols[0].append(left := uno.Paragraph('Column 1'))
    cols[1].append(right := uno.Paragraph('Column 2'))
    cols[0].delete()
    page.reload()

    cols = cast(uno.Columns, page.children[0])
    col = cast(uno.Column, cols.children[0])
    paragraph = cast(uno.Paragraph, col.children[0])
    assert paragraph == right
    assert left.reload().is_deleted

    with pytest.raises(IndexError):
        cols.add_column(index=-1)
    with pytest.raises(IndexError):
        cols.add_column(index=len(cols.children) + 1)

    cols.add_column(index=1)
    cols[1].append(new_right := uno.Paragraph('New Column 1'))
    page.reload()

    cols = cast(uno.Columns, page.children[0])
    left_col, right_col = cast(list[uno.Column], cols.children)
    assert left_col.children == (right,)
    assert right_col.children == (new_right,)

    with pytest.raises(InvalidAPIUsageError):
        cols.append(uno.Paragraph('This is a paragraph'))


@pytest.mark.vcr()
def test_modify_column_blocks_width_ratios(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for modifying column blocks with width ratios')
    with pytest.raises(TypeError):
        uno.Columns((0.5, 'a', 0.5))  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        uno.Columns((1, -2, 3))

    cols = uno.Columns((1, 3))
    page.append(cols)
    assert cols[0].width_ratio == 0.25
    assert cols[1].width_ratio == 0.75
    cols[0].append(uno.Paragraph('Column 1'))
    cols[1].append(uno.Paragraph('Column 2'))

    cols.add_column(index=1)
    cols[1].append(uno.Paragraph('Column 1.5'))
    assert cols[1].width_ratio is None

    cols.width_ratios = (1, 6, 1)
    assert cols.width_ratios == (0.125, 0.75, 0.125)

    with pytest.raises(ValueError):
        cols.width_ratios = (1, 2, 3, 4)

    with pytest.raises(TypeError):
        cols.width_ratios = (1, 'a', 3)

    with pytest.raises(ValueError):
        cols.width_ratios = (-1, 2, 3)


@pytest.mark.vcr()
def test_modify_table(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for modifying table blocks')
    table = uno.Table(2, 3, header_row=True)
    table[0, 0] = 'Cell 0, 0'
    table[0, 1] = 'Cell 0, 1'
    table[0, 2] = 'Cell 0, 2'
    table[1] = ('Cell 1, 0', 'Cell 1, 1', 'Cell 1, 2')
    page.append(table)
    page.reload()

    assert table[0] == ('Cell 0, 0', 'Cell 0, 1', 'Cell 0, 2')
    assert table[1, 0] == 'Cell 1, 0'
    assert table[1, 1] == 'Cell 1, 1'
    assert table[1, 2] == 'Cell 1, 2'

    table.insert_row(1, ('New Cell 1, 0', 'New Cell 1, 1', 'New Cell 1, 2'))
    table.append_row(('New Cell 3, 0', 'New Cell 3, 1', 'New Cell 3, 2'))

    page.reload()
    assert table[1] == ('New Cell 1, 0', 'New Cell 1, 1', 'New Cell 1, 2')
    assert table[2] == ('Cell 1, 0', 'Cell 1, 1', 'Cell 1, 2')
    assert table[3] == ('New Cell 3, 0', 'New Cell 3, 1', 'New Cell 3, 2')

    table[2].delete()
    page.reload()
    assert table[2] == ('New Cell 3, 0', 'New Cell 3, 1', 'New Cell 3, 2')

    table.has_header_col = True
    page.reload()
    assert table.has_header_col

    table.has_header_row = True
    page.reload()
    assert table.has_header_row


@pytest.mark.vcr()
def test_insert_after_replace_block(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for inserting after and replacing blocks')
    orig_target = notion.create_page(parent=root_page, title='Original Target')
    new_target = notion.create_page(parent=root_page, title='New Target')
    page.append([heading := uno.Heading1('My new page'), link := uno.LinkToPage(orig_target)])

    with pytest.raises(InvalidAPIUsageError):
        link.page = new_target

    heading.insert_after(paragraph := uno.Paragraph('This is a paragraph'))
    link.replace(new_link := uno.LinkToPage(new_target))

    page.reload()

    assert page.children == (heading, paragraph, new_link)
    assert link.is_deleted

    divider = uno.Divider()
    table = uno.Table(2, 2)

    paragraph.insert_after([divider, table])
    assert page.children == (heading, paragraph, divider, table, new_link)

    page.reload()

    assert page.children == (heading, paragraph, divider, table, new_link)

    with pytest.raises(InvalidAPIUsageError):
        divider.insert_after(divider)

    with pytest.raises(InvalidAPIUsageError):
        divider.replace(table)

    table.delete()

    with pytest.raises(InvalidAPIUsageError):
        divider.insert_after(table)

    with pytest.raises(InvalidAPIUsageError):
        divider.replace(divider)


@pytest.mark.vcr()
def test_nested_bullet_items(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for nested bullet points')
    page.append(uno.BulletedItem('First bullet'))
    page.append(second_bullet := uno.BulletedItem('Second bullet'))
    second_bullet.append(uno.BulletedItem('Nested bullet'))


@pytest.mark.vcr()
def test_color_code_block(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='Page for color code block')
    code_block = uno.Code('print("Hello, world!")', language='python')
    assert code_block.obj_ref.code.rich_text[0].annotations.color is Unset  # type: ignore[union-attr]
    page.append(code_block)

    assert page.children == (code_block,)
    assert code_block.language == 'python'
    # Note that None was replaced with Color.DEFAULT by the API. Sending it directly
    # would have prevented the python code coloring from being applied in the Notion UI.
    assert code_block.obj_ref.code.rich_text[0].annotations.color is uno.Color.DEFAULT  # type: ignore[union-attr]


@pytest.mark.vcr()
def test_offline_block_assembly(root_page: uno.Page, notion: uno.Session) -> None:
    blocks: list[uno.Block] = [
        p := uno.Paragraph('This is the first block.'),
        q := uno.Quote('This is a quote.'),
        b := uno.BulletedItem('This is a bullet point.'),
        c := uno.Callout('This is a callout.'),
    ]
    p.append(cp := uno.Paragraph('This is a child paragraph.'))
    q.append(cq := uno.Paragraph('This is a child paragraph of the quote.'))
    b.append(cb := uno.Paragraph('This is a child paragraph of the bullet point.'))
    c.append(cc := uno.Paragraph('This is a child paragraph of the callout.'))

    page = notion.create_page(parent=root_page, title='Page for offline assembly', blocks=blocks)

    assert page.children == (p, q, b, c)
    assert p.children == (cp,)
    assert q.children == (cq,)
    assert b.children == (cb,)
    assert c.children == (cc,)

    page.reload()

    assert page.children == (p, q, b, c)
    assert p.children == (cp,)
    assert q.children == (cq,)
    assert b.children == (cb,)
    assert c.children == (cc,)

    callout = uno.Heading1('This is a Heading.', toggleable=True)
    with pytest.raises(InvalidAPIUsageError):
        callout.append(uno.Paragraph('This is a child paragraph.'))


@pytest.mark.vcr()
def test_block_equality_and_hash(root_page: uno.Page, notion: uno.Session) -> None:
    para1 = uno.Paragraph(text='Some text')
    para2 = uno.Paragraph(text='Different text')
    para1a = uno.Paragraph(text='Some text')

    assert para1 != para2
    assert hash(para1) != hash(para2)
    assert para1 == para1a
    assert hash(para1) == hash(para1a)

    with pytest.raises(UnsetError):
        assert para1.id != para2.id

    page = notion.create_page(parent=root_page, title='Page for testing block equality and hash')
    page.append([para1, para2, para1a])

    assert para1.id != para2.id
    assert para1.id != para1a.id

    assert para1 != para2
    assert para1 != para1a  # same content but now different id!
    assert hash(para1) != hash(para2)
    assert hash(para1) != hash(para1a)


def test_rt_default_color() -> None:
    para_1 = uno.Paragraph(text='Hello')
    para_2 = uno.Paragraph(text='')
    rich_text = uno.text(text='Hello')
    para_2.rich_text = rich_text

    assert para_1.obj_ref.serialize_for_api() == para_2.obj_ref.serialize_for_api()


@pytest.mark.vcr()
def test_max_children_length(root_page: uno.Page, notion: uno.Session) -> None:
    n_blocks = int(1.2 * uno_blocks.MAX_BLOCK_CHILDREN)
    blocks = [uno.Paragraph(f'Paragraph {i}') for i in range(n_blocks)]
    page = notion.create_page(parent=root_page, title='Page for testing max children length', blocks=blocks)
    assert len(page.children) == len(blocks)

    ablocks = [uno.Paragraph(f'Another Paragraph {i}') for i in range(n_blocks)]
    page.append(ablocks, after=page.children[2])
    assert page.children[3] == ablocks[0]
    assert len(page.children) == 2 * n_blocks
    assert page.children[3 + n_blocks] == blocks[3]


@pytest.mark.vcr()
def test_max_nesting_level(root_page: uno.Page, notion: uno.Session) -> None:
    n_blocks = int(1.2 * uno_blocks.MAX_BLOCK_CHILDREN)
    blocks = [uno.BulletedItem(f'Point {i}') for i in range(n_blocks)]
    # add a 1st level of nesting
    blocks[0].append([uno.BulletedItem(f'Nested Point {i}') for i in range(n_blocks)])
    # add a 2nd level of nesting
    blocks[0].children[0].append([uno.BulletedItem(f'Deeply Nested Point {i}') for i in range(n_blocks)])  # type: ignore[attr-defined]

    page = notion.create_page(
        parent=root_page, title='Page for testing max nesting level', blocks=[uno.Paragraph('Intro')]
    )
    page.append(blocks)

    assert len(page.children) == n_blocks + 1
    assert len(page.children[1].children) == n_blocks  # type: ignore[attr-defined]
    assert len(page.children[1].children[0].children) == n_blocks  # type: ignore[attr-defined]

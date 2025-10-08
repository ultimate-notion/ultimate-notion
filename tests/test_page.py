from __future__ import annotations

import re
import time
from textwrap import dedent

import pytest

import ultimate_notion as uno
from tests.conftest import assert_eventually
from ultimate_notion.blocks import Block
from ultimate_notion.emoji import CustomEmoji
from ultimate_notion.obj_api.props import MAX_ITEMS_PER_PROPERTY
from ultimate_notion.page import Page


@pytest.mark.vcr()
def test_parent(page_hierarchy: tuple[Page, Page, Page]) -> None:
    root_page, l1_page, l2_page = page_hierarchy
    assert isinstance(root_page, uno.Page)
    assert isinstance(l1_page, uno.Page)
    assert isinstance(l2_page, uno.Page)

    assert root_page.parent is uno.Workspace
    assert l2_page.parent == l1_page
    assert l1_page.parent == root_page
    assert isinstance(l2_page.parent, uno.Page)
    assert l2_page.parent.parent == root_page


@pytest.mark.vcr()
def test_ancestors(page_hierarchy: tuple[uno.Page, ...]) -> None:
    root_page, l1_page, l2_page = page_hierarchy
    assert l2_page.ancestors == (root_page, l1_page)


@pytest.mark.vcr()
def test_delete_restore_page(notion: uno.Session, root_page: uno.Page) -> None:
    page = notion.create_page(root_page)
    assert not page.is_deleted
    page.delete()
    assert page.is_deleted
    page.restore()
    assert not page.is_deleted


@pytest.mark.vcr()
def test_reload_page(notion: uno.Session, root_page: uno.Page) -> None:
    page = notion.create_page(root_page)
    old_obj_id = id(page.obj_ref)
    page.reload()
    assert old_obj_id != id(page.obj_ref)


@pytest.mark.vcr()
def test_parent_subpages(notion: uno.Session, root_page: uno.Page) -> None:
    parent = notion.create_page(root_page, title='Parent')
    child1 = notion.create_page(parent, title='Child 1')
    child2 = notion.create_page(parent, title='Child 2')

    assert child1.parent == parent
    assert child2.parent == parent
    assert parent.subpages == [child1, child2]
    assert all(isinstance(page, uno.Page) for page in parent.subpages)
    assert child1.ancestors == (root_page, parent)


@pytest.mark.vcr()
def test_parent_children(intro_page: uno.Page) -> None:
    assert all(isinstance(block, Block) for block in intro_page.children)


@pytest.mark.vcr()
def test_icon_attr(notion: uno.Session, root_page: uno.Page) -> None:
    new_page = notion.create_page(parent=root_page, title='My new page with icon')

    assert new_page.icon is None
    emoji_icon = '🐍'
    new_page.icon = emoji_icon  # test automatic conversation
    assert isinstance(new_page.icon, uno.Emoji)
    assert new_page.icon == emoji_icon

    new_page.icon = uno.Emoji(emoji_icon)
    assert isinstance(new_page.icon, uno.Emoji)
    assert new_page.icon == emoji_icon

    # clear cache and retrieve the page again to be sure it was udpated on the server side
    del notion.cache[new_page.id]
    new_page = notion.get_page(new_page.id)
    assert new_page.icon == uno.Emoji(emoji_icon)

    notion_icon_url = 'https://www.notion.so/icons/snake_purple.svg'
    new_page.icon = uno.url(notion_icon_url)
    assert isinstance(new_page.icon, uno.AnyFile)
    assert new_page.icon == uno.ExternalFile(url=notion_icon_url)

    new_page.reload()
    assert new_page.icon == uno.ExternalFile(url=notion_icon_url)

    new_page.icon = None
    new_page.reload()
    assert new_page.icon is None


@pytest.mark.vcr()
def test_cover_attr(notion: uno.Session, root_page: uno.Page) -> None:
    new_page = notion.create_page(parent=root_page, title='My new page with cover')

    assert new_page.cover is None
    cover_file = uno.url('https://www.notion.so/images/page-cover/woodcuts_2.jpg')
    new_page.cover = cover_file
    assert isinstance(new_page.cover, uno.ExternalFile)
    assert new_page.cover == cover_file

    new_page.reload()
    assert new_page.cover == cover_file

    new_page.cover = None
    new_page.reload()
    assert new_page.cover is None


@pytest.mark.vcr()
def test_title_attr(notion: uno.Session, root_page: uno.Page) -> None:
    new_page = notion.create_page(parent=root_page)

    assert new_page.title is None

    title = 'My new title'
    new_page.title = title  # test automatic conversation
    assert new_page.title == title

    new_page.title = uno.text(title)
    assert new_page.title == title

    new_page.reload()
    assert new_page.title == uno.text(title)

    new_page.title = None
    new_page.reload()
    assert new_page.title is None

    new_page.title = ''
    new_page.reload()
    assert new_page.title is None


@pytest.mark.vcr()
def test_created_edited_by(notion: uno.Session, root_page: uno.Page) -> None:
    myself = notion.whoami()
    florian = notion.search_user('Florian Wilhelm').item()
    assert root_page.created_by == florian
    assert root_page.last_edited_by in {myself, florian}


@pytest.mark.vcr()
def test_page_to_markdown(md_page: uno.Page) -> None:
    def remove_query_string(line: str) -> str:
        line = re.sub(r'\?.*?\]', ']', line)
        line = re.sub(r'prod.*?\)', ')', line)
        return line

    exp_output = dedent(
        """
        # Markdown Test

        ## Headline 1
        ### Headline 2
        #### Headline 3
        ---

        ## Toggle Headline 1
        ### Toggle Headline 2
        #### Toggle Headline 3
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

        This is an emoji! 😀😀
        $$
        |x|=\\begin{cases}x, &\\quad x \\geq 0\\\\-x, &\\quad x < 0\\end{cases}
        $$

        ```python
        # Python Code
        import ultimate_notion
        ```
        [Caption](https://picsum.photos/300/300)

        ![1004-300x300.jpg](https://)

        [📎 logo_with_text.svg](https://ultimate-notion.com/latest/assets/images/logo_with_text.svg)

        <audio controls><source src="https://samplelib.com/lib/preview/mp3/sample-3s.mp3" type="audio/mpeg"></audio>

        ### Unsupported Stuff in Markdown
        <!--- column 1 -->
        Column 1
        <!--- column 2 -->
        Column
        ```{toc}
        ```
        Tests / Markdown Test

        [📄 **<u>Markdown SubPage Test</u>**](https://www.notion.so/Markdown-SubPage-Test-67ad5240b1b944679b073ef3ebbbc755)

        <!--- original block -->
        This is the original Paragraph on Page
        <!--- synced block -->
        This is the original Paragraph on SubPage
        [**↗️ <u>Markdown SubPage Test</u>**](https://www.notion.so/Markdown-SubPage-Test-67ad5240b1b944679b073ef3ebbbc755)

        <kbd>Unsupported block</kbd>

        <kbd>Unsupported block</kbd>
    """
    )
    markdown = md_page.to_markdown().strip().split('\n')
    idx = 53
    markdown[idx] = remove_query_string(markdown[idx])

    for exp, act in zip(exp_output.strip().split('\n'), markdown, strict=True):
        assert exp == act


@pytest.mark.vcr()
def test_parent_db(notion: uno.Session, root_page: uno.Page) -> None:
    db = notion.create_db(root_page)
    db.title = 'Parent DB'
    page_in_db = db.create_page()
    assert page_in_db.in_db
    assert page_in_db.parent_db is db

    page_not_in_db = notion.create_page(root_page, 'Page not in DB')
    assert not page_not_in_db.in_db
    assert page_not_in_db.parent_db is None


@pytest.mark.vcr()
def test_more_than_max_refs_per_relation_property(notion: uno.Session, root_page: uno.Page) -> None:
    class Item(uno.Schema, db_title='Item DB for max relation items'):
        """Database of all items"""

        name = uno.PropType.Title('Name')
        price = uno.PropType.Number('Price', format=uno.NumberFormat.DOLLAR)
        bought_by = uno.PropType.Relation('Bought by')

    class Customer(uno.Schema, db_title='Customer DB for max relation items'):
        """Database for customers"""

        name = uno.PropType.Title('Name')
        purchases = uno.PropType.Relation('Items Purchased', schema=Item, two_way_prop=Item.bought_by)

    item_db = notion.create_db(parent=root_page, schema=Item)
    customer_db = notion.create_db(parent=root_page, schema=Customer)
    customer = customer_db.create_page(name='Customer 1')

    n_prop_items = MAX_ITEMS_PER_PROPERTY + 5
    for i in range(1, n_prop_items + 1):
        item_db.create_page(name=f'Item {i}', price=i * 10, bought_by=customer)

    customer.reload()  # reload to get the updated relation
    time.sleep(3)  # wait for the changes to be applied on the server side

    assert_eventually(lambda: len(customer.props.purchases) == n_prop_items)


@pytest.mark.vcr()
def test_more_than_max_mentions_per_text_property(notion: uno.Session, root_page: uno.Page, person: uno.User) -> None:
    # According to the Notion API (see below), this test should fail but it doesn't.
    # Source: https://developers.notion.com/reference/retrieve-a-page#limits
    class Item(uno.Schema, db_title='Item DB for max text items'):
        """Database of all items"""

        name = uno.PropType.Title('Name')
        desc = uno.PropType.Text('Description')

    notion.create_db(parent=root_page, schema=Item)

    # generate a text that will have internally more than MAX_ITEMS_PER_PROPERTY mentions parts
    n_mentions = 2 * MAX_ITEMS_PER_PROPERTY
    text = uno.text('Who is the best programmer? ;-) ')
    text += uno.join([uno.mention(person) for _ in range(n_mentions)], delim=', ')

    item = Item.create(name=text, desc=text)
    item.reload()  # reload to clear cache and retrieve the page again

    assert len(item.props.name.mentions) == n_mentions
    assert len(item.props.desc.mentions) == n_mentions


@pytest.mark.vcr()
def test_embed_blocks(notion: uno.Session, embed_page: uno.Page) -> None:
    blocks = embed_page.children
    assert len(blocks) >= 4
    md = embed_page.to_markdown()
    assert md.strip().split('\n')[-1] == '<kbd>↗️ Linked database (unsupported)</kbd>'


@pytest.mark.vcr()
def test_option_page_props(notion: uno.Session, root_page: uno.Page) -> None:
    select_options = [
        uno.Option(name='Open', color=uno.Color.GRAY),
        uno.Option(name='In Progress', color=uno.Color.BLUE),
        uno.Option(name='Blocked', color=uno.Color.RED),
        uno.Option(name='Closed', color=uno.Color.GREEN),
    ]
    multi_select_options = [
        uno.Option(name='Option 1', color=uno.Color.DEFAULT),
        uno.Option(name='Option 2', color=uno.Color.PINK),
    ]

    class Schema(uno.Schema, db_title='Option Page Props Test'):
        """Schema for testing option page props"""

        title = uno.PropType.Title('Title')
        status = uno.PropType.Select('Status', options=select_options)
        multi_status = uno.PropType.MultiSelect('Multi Status', options=multi_select_options)

    notion.create_db(parent=root_page, schema=Schema)
    page1 = Schema.create(title='Page 1', status='Open', multi_status=['Option 1'])
    page2 = Schema.create(title='Page 2', status='In Progress', multi_status=['Option 1', 'Option 2'])

    s_options = {opt.name: opt for opt in select_options}
    ms_options = {opt.name: opt for opt in multi_select_options}

    assert page1.props.status == s_options['Open']
    page1.props.status = s_options['Blocked']
    assert page1.props.status.name == 'Blocked'
    page1.props.status = 'Closed'
    assert page1.props.status.name == 'Closed'

    assert page2.props.multi_status == [ms_options['Option 1'], ms_options['Option 2']]
    page2.props.multi_status = [ms_options['Option 1']]
    assert page2.props.multi_status == [ms_options['Option 1']]
    page2.props.multi_status = 'Option 2'
    assert page2.props.multi_status == [ms_options['Option 2']]
    page2.props.multi_status = ['Option 1', 'Option 2']
    assert page2.props.multi_status == [ms_options['Option 1'], ms_options['Option 2']]


@pytest.mark.vcr()
def test_custom_emoji_icon(notion: uno.Session, root_page: uno.Page, custom_emoji_page: uno.Page) -> None:
    """Test custom emoji on a page."""
    assert isinstance(custom_emoji_page.icon, CustomEmoji)
    assert custom_emoji_page.icon.name == 'ultimate-notion'
    assert str(custom_emoji_page.icon) == ':ultimate-notion:'

    exp_md = dedent(
        """
        # Custom Emoji Page

        This page has a custom emoji :ultimate-notion: compared to 🚀.
        💡 Callout block without an emoji
        """
    ).strip()

    assert custom_emoji_page.to_markdown().strip() == exp_md

    page = notion.create_page(
        parent=root_page,
        title='Page with Custom Emoji Icon',
    )
    page.icon = custom_emoji_page.icon
    assert isinstance(page.icon, CustomEmoji)

    text = 'This page has a user-added custom emoji icon '
    page.append(uno.Paragraph(uno.text(text) + custom_emoji_page.icon))
    assert page.children[0].to_markdown() == text + f'{custom_emoji_page.icon}'

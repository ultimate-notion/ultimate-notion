from __future__ import annotations

from typing import cast

import pendulum as pnd
import pytest

import ultimate_notion as uno
from ultimate_notion import Database, Page, Session, User
from ultimate_notion.blocks import TextBlock
from ultimate_notion.schema import MultiSelect, Select, Status


@pytest.mark.vcr()
def test_status_options_groups(all_props_db: Database):
    status_prop_type = cast(Status, all_props_db.schema.get_prop('Status').type)
    all_options = ['Not started', 'In progress', 'Done']
    assert [option.name for option in status_prop_type.options] == all_options

    all_groups = ['To-do', 'In progress', 'Complete']
    assert [group.name for group in status_prop_type.groups] == all_groups

    completed_options = status_prop_type.groups[2].options
    assert [option.name for option in completed_options] == ['Done']


@pytest.mark.vcr()
def test_select_options(all_props_db: Database):
    select_prop_type = cast(Select, all_props_db.schema.get_prop('Select').type)
    all_options = ['Option1', 'Option2']
    assert [option.name for _, option in select_prop_type.options.items()] == all_options


@pytest.mark.vcr()
def test_multi_select_options(all_props_db: Database):
    multi_select_prop_type = cast(MultiSelect, all_props_db.schema.get_prop('Multi-Select').type)
    all_options = ['MultiOption1', 'MultiOption2']
    assert [option.name for _, option in multi_select_prop_type.options.items()] == all_options


@pytest.mark.vcr()
def test_rich_text_md(md_text_page: Page):
    """These markdowns were tested with https://stackedit.io/app#"""
    correct_mds = [
        'here is something **very** *simpel* and <u>underlined</u> as well as `code`',
        '**here is a sentence that was bolded *then* typed.**',
        'here is a test sentence with ~~many **different *styles*.**~~',
        'here is another test with ~~many *different **styles**.*~~',
        'here is one more with a *strange **style*** **combination**',
        'here is one with an inline **~~equa-*tion*~~ *$E=mc^2$ and*** no block equation',
        (
            'and here is one with ~~***person** mention [@Florian Wilhelm]()*~~ and **page mention '
            '↗[Markdown Text Test](https://www.notion.so/0c8ea7f1c7ca4abb8890085c0fac383b)** '
        ),
        'here is one **stretching over *many\n~~many~~*\n~~lines~~**',
        # ToDo: This is not 100% right as line breaks in code blocks are ignored in Markdown.
        # Thus '\n' in the last code block will be ignored and the code will be in one line.
        # To Fix this we would have to break rich_texts into multiple code blocks.
        'This is code, e.g. **`python` code\nnow stretching `over\nmany lines`**',
        'This is a [li**n**k](https://google.de/) and a ~~first~~ an~~d <u>second</u> stroke~~ through<u> word.</u>',
        'Half a [lin](https://google.de/)[k](https://amazon.com/) for two destinations',
        '✨Magic ✨',
    ]
    for idx, block in enumerate(md_text_page.children):
        assert isinstance(block, TextBlock)
        our_md = block.rich_text.to_markdown()
        assert our_md == correct_mds[idx]


@pytest.mark.vcr()
def test_mention(person: User, root_page: Page, md_text_page: Page, all_props_db: Database, notion: Session):
    user_mention = uno.Mention(person)
    page_mention = uno.Mention(md_text_page)
    db_mention = uno.Mention(all_props_db)
    date_mention = uno.Mention(pnd.datetime(2022, 1, 1))

    page = notion.create_page(parent=root_page, title='Mention blocks Test')
    paragraph = uno.Paragraph(user_mention + ' : ' + page_mention + ' : ' + db_mention + ' : ' + date_mention)
    page.append(paragraph)
    exp_text = (
        '[@Florian Wilhelm]() : ↗[Markdown Text Test](https://www.notion.so/0c8ea7f1c7ca4abb8890085c0fac383b)'
        ' : ↗[All Properties DB](https://www.notion.so/4fa8756fa0da4efe9c484d6a323b69f8)'
        ' : [2022-01-01T00:00:00.000+00:00]()'
    )
    assert page.to_markdown() == exp_text


@pytest.mark.vcr()
def test_rich_text_bases(person: User, root_page: Page, notion: Session):
    text: uno.AnyText = uno.Text('This is an equation: ', color=uno.Color.BLUE)
    text += uno.Math('E=mc^2', bold=True)
    text += uno.Text(' and this is a mention: ', href='https://ultimate-notion.com')
    text += uno.Mention(person)
    assert isinstance(text, uno.RichText)

    page = notion.create_page(parent=root_page, title='RichText Test')
    page.append(uno.Paragraph(text))
    exp_text = (
        'This is an equation: **$E=mc^2$** [and this is a mention:](https://ultimate-notion.com/) '
        '[@Florian Wilhelm]()'
    )
    assert page.to_markdown() == exp_text

    notion.cache.clear()
    page = notion.get_page(page.id)
    assert page.to_markdown() == exp_text

from __future__ import annotations

import pendulum as pnd
import pytest

import ultimate_notion as uno
from ultimate_notion import Database, Page, Session, User
from ultimate_notion.blocks import TextBlock
from ultimate_notion.text import camel_case, decapitalize, is_url, snake_case


def test_decapitalize():
    assert decapitalize('') == ''
    assert decapitalize('34f') == '34f'
    assert decapitalize('small') == 'small'
    assert decapitalize('Small') == 'small'
    assert decapitalize('SMall') == 'sMall'


def test_snake_case():
    assert snake_case('Notion is cool') == 'notion_is_cool'
    assert snake_case('Notion is cool ') == 'notion_is_cool'
    assert snake_case('Notion is cool! ') == 'notion_is_cool'
    assert snake_case(' Notion is cool ') == 'notion_is_cool'
    assert snake_case('!Notion is cool!') == 'notion_is_cool'
    assert snake_case('!Notion Is COOL!') == 'notion_is_cool'
    assert snake_case('notion_is_cool') == 'notion_is_cool'
    assert snake_case('123notion is cool') == 'notion_is_cool'
    assert snake_case('') == ''


def test_camel_case():
    assert camel_case('Notion is cool') == 'NotionIsCool'
    assert camel_case('Notion is cool ') == 'NotionIsCool'
    assert camel_case('Notion is cool! ') == 'NotionIsCool'
    assert camel_case(' Notion is cool ') == 'NotionIsCool'
    assert camel_case('!Notion is cool!') == 'NotionIsCool'
    assert camel_case('!Notion Is COOL!') == 'NotionIsCool'
    assert camel_case('notion_is_cool') == 'NotionIsCool'
    assert camel_case('123notion is cool') == 'NotionIsCool'
    assert camel_case('') == ''


def test_is_url():
    assert is_url('https://www.example.com')
    assert is_url('http://www.example.com')
    assert not is_url('http://')
    assert not is_url('')
    assert not is_url('www.example.com')


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

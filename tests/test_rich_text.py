from __future__ import annotations

import pendulum as pnd
import pytest

import ultimate_notion as uno
from ultimate_notion.rich_text import camel_case, decapitalize, is_url, snake_case


def test_decapitalize() -> None:
    assert decapitalize('') == ''
    assert decapitalize('34f') == '34f'
    assert decapitalize('small') == 'small'
    assert decapitalize('Small') == 'small'
    assert decapitalize('SMall') == 'sMall'


def test_snake_case() -> None:
    assert snake_case('Notion is cool') == 'notion_is_cool'
    assert snake_case('Notion is cool ') == 'notion_is_cool'
    assert snake_case('Notion is cool! ') == 'notion_is_cool'
    assert snake_case(' Notion is cool ') == 'notion_is_cool'
    assert snake_case('!Notion is cool!') == 'notion_is_cool'
    assert snake_case('!Notion Is COOL!') == 'notion_is_cool'
    assert snake_case('notion_is_cool') == 'notion_is_cool'
    assert snake_case('123notion is cool') == 'notion_is_cool'
    assert snake_case('') == ''


def test_camel_case() -> None:
    assert camel_case('Notion is cool') == 'NotionIsCool'
    assert camel_case('Notion is cool ') == 'NotionIsCool'
    assert camel_case('Notion is cool! ') == 'NotionIsCool'
    assert camel_case(' Notion is cool ') == 'NotionIsCool'
    assert camel_case('!Notion is cool!') == 'NotionIsCool'
    assert camel_case('!Notion Is COOL!') == 'NotionIsCool'
    assert camel_case('notion_is_cool') == 'NotionIsCool'
    assert camel_case('123notion is cool') == 'NotionIsCool'
    assert camel_case('') == ''


def test_is_url() -> None:
    assert is_url('https://www.example.com')
    assert is_url('http://www.example.com')
    assert not is_url('http://')
    assert not is_url('')
    assert not is_url('www.example.com')


@pytest.mark.vcr()
def test_mention(
    person: uno.User, root_page: uno.Page, md_text_page: uno.Page, all_props_db: uno.Database, notion: uno.Session
) -> None:
    user_mention = uno.mention(person)
    page_mention = uno.mention(md_text_page)
    db_mention = uno.mention(all_props_db)
    date_mention = uno.mention(pnd.datetime(2022, 1, 1))

    page = notion.create_page(parent=root_page, title='Mention blocks Test')
    paragraph = uno.Paragraph(user_mention + ' : ' + page_mention + ' : ' + db_mention + ' : ' + date_mention)
    page.append(paragraph)
    exp_text = (
        '[@Florian Wilhelm]() : ↗[Markdown Text Test](https://www.notion.so/0c8ea7f1c7ca4abb8890085c0fac383b)'
        ' : ↗[All Properties DB](https://www.notion.so/4fa8756fa0da4efe9c484d6a323b69f8)'
        ' : [2022-01-01T00:00:00.000+00:00]()'
    )
    assert page.children[0].to_markdown() == exp_text


@pytest.mark.vcr()
def test_rich_text_bases(person: uno.User, root_page: uno.Page, notion: uno.Session) -> None:
    text = uno.text('This is an equation: ', color=uno.Color.BLUE)
    text += uno.math('E=mc^2', bold=True)
    text += uno.text(' and this is a mention: ', href='https://ultimate-notion.com/')
    text += uno.mention(person)
    exp_text = (
        'This is an equation: **$E=mc^2$** [and this is a mention:](https://ultimate-notion.com/) '
        '[@Florian Wilhelm]()'
    )
    assert text.to_markdown() == exp_text

    page = notion.create_page(parent=root_page, title='RichText Test')
    page.append(uno.Paragraph(text))
    assert page.children[0].to_markdown() == exp_text

    notion.cache.clear()
    page = notion.get_page(page.id)
    assert page.children[0].to_markdown() == exp_text


def test_rich_text() -> None:
    text = uno.text('Simple Text')
    assert str(text) == 'Simple Text'
    text += uno.text(' and a bold text', bold=True)
    assert str(text) == 'Simple Text and a bold text'
    assert text.to_markdown() == 'Simple Text **and a bold text**'
    assert uno.text(text).to_markdown() == 'Simple Text and a bold text'  # converted to plain text
    # ToDo: Extend this test!

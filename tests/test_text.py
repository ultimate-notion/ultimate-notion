from __future__ import annotations

from uuid import UUID, uuid4

from ultimate_notion.text import camel_case, decapitalize, extract_id, snake_case


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


def test_extract_id():
    """Make sure we can parse UUID's with and without dashes."""

    page_id = uuid4()

    assert UUID(extract_id(str(page_id))) == page_id

    for base_url in ('https://www.notion.so', 'https://notion.so'):
        page_url = f'{base_url}/{page_id}'
        assert UUID(extract_id(page_url)) == page_id

        page_url = f'{base_url}/page-title-{page_id}'
        assert UUID(extract_id(page_url)) == page_id

        block_id = uuid4()
        page_url = f'{base_url}/username/page-title-{page_id}#{block_id!s}'
        assert UUID(extract_id(page_url)) == block_id

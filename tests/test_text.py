from ultimate_notion.text import camel_case, decapitalize, snake_case


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

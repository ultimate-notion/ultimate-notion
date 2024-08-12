from __future__ import annotations

from ultimate_notion import templates


def test_get_template():
    templates.get_template('page.html')
    templates.get_template('page.html', relative_to='ultimate_notion.templates')
    templates.get_template('page.html', relative_to=templates)


def test_page_html():
    content = 'this is my content'
    title = 'this is my title'
    assert content in templates.page_html(content)
    assert title in templates.page_html('content', title=title)

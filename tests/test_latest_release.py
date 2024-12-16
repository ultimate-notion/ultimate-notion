"""This test module only tests the latest release of Ultimate-Notion.

This is to ensure that the latest release is working as expected as the Notion API is subject to frequent changes.
We only test the most basic functionality of the library to ensure that the latest release is working as expected.
"""

from __future__ import annotations

import pytest

import ultimate_notion as uno
from tests.conftest import exec_pyfile


@pytest.fixture(scope='module', autouse=True)
def notion_cleanups() -> None:
    """Overwrites fixture from conftest.py to avoid an open session."""


@pytest.mark.check_latest_release
def test_getting_started() -> None:
    exec_pyfile('examples/getting_started.py')


@pytest.mark.check_latest_release
def test_create_simple_task_db() -> None:
    exec_pyfile('examples/simple_taskdb.py')


@pytest.mark.check_latest_release
def test_page_to_markdown(md_page: uno.Page) -> None:
    md_page.to_markdown()  # just check if it runs without errors


@pytest.mark.check_latest_release
def test_create_page(root_page: uno.Page, notion: uno.Session) -> None:
    page = notion.create_page(parent=root_page, title='New page test for latest release')
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

    assert page.children == (h1, h2, h21, h3, h4)

"""Fixtures for Ultimate-Notion unit tests.

Set `ENV_NOTION_AUTH_TOKEN` for tests intracting with the Notion API.
"""

import os

import pytest

import ultimate_notion
from ultimate_notion import schema
from ultimate_notion.session import ENV_NOTION_AUTH_TOKEN


@pytest.fixture(scope='module')
def vcr_config():
    """Configure pytest-vcr."""
    # ToDo: See if this is still important

    def remove_headers(response):
        response['headers'] = {}
        return response

    return {
        'filter_headers': [
            ('authorization', 'secret...'),
            ('user-agent', None),
        ],
        'before_record_response': remove_headers,
    }


@pytest.fixture(scope="session")
def notion():
    """Return the notion session used for live testing.

    This fixture depends on the `NOTION_AUTH_TOKEN` environment variable. If it is not
    present, this fixture will skip the current test.
    """
    if os.getenv(ENV_NOTION_AUTH_TOKEN) is None:
        msg = f'{ENV_NOTION_AUTH_TOKEN} not defined! Use `export {ENV_NOTION_AUTH_TOKEN}=secret_...`'
        raise RuntimeError(msg)

    with ultimate_notion.Session() as notion:
        yield notion


@pytest.fixture(scope="session")
def contacts_db(notion):
    """Return a test database"""
    return notion.search_db('Contacts').item()


@pytest.fixture(scope="session")
def root_page(notion):
    """Return the page reference used as parent page for live testing"""
    return notion.search_page('Tests', exact=True).item()


@pytest.fixture
def simple_db(notion, root_page):
    """Simple database of articles"""

    class Article(schema.PageSchema):
        name = schema.Property('Name', schema.Title())
        cost = schema.Property('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Property('Description', schema.Text())

    db = notion.create_db(parent=root_page, schema=Article, title='Articles')
    yield db
    notion.delete_db(db)


@pytest.fixture(scope="session")
def page_hierarchy(notion, root_page):
    """Simple hierarch of 3 pages nested in eachother: root -> l1 -> l2"""
    l1_page = notion.create_page(parent=root_page, title='level_1')
    l2_page = notion.create_page(parent=l1_page, title='level_2')
    yield root_page, l1_page, l2_page
    notion.delete_page(l2_page)
    notion.delete_page(l1_page)


@pytest.fixture(scope="session", autouse=True)
def test_cleanups(notion, root_page):
    """Delete all databases and pages in the root_page before we start"""
    for db in notion.search_db():
        if db.parents[0] == root_page:
            notion.delete_db(db)
    for page in notion.search_page():
        if page.parents and page.parents[0] == root_page:
            notion.delete_page(page)

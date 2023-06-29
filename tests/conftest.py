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


@pytest.fixture
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


@pytest.fixture
def contacts_db(notion):
    """Return a test database"""
    return notion.search_db('Contacts').item()


@pytest.fixture
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

    db = notion.create_db(parent_page=root_page, schema=Article, title='Articles')
    yield db
    notion.delete_db(db)

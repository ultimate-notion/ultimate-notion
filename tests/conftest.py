"""Fixtures for Ultimate-Notion unit tests.

Set `ENV_NOTION_AUTH_TOKEN` for tests intracting with the Notion API.
"""

import os

import pytest

import ultimate_notion
from ultimate_notion import Session, schema
from ultimate_notion.page import Page
from ultimate_notion.session import ENV_NOTION_AUTH_TOKEN

# Manually created DB in Notion with all possible columns including AI columns!
ALL_COL_DB = 'All Columns DB'
WIKI_DB = 'Wiki DB'


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


@pytest.fixture(scope='session')
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


@pytest.fixture(scope='session')
def contacts_db(notion: Session):
    """Return a test database"""
    return notion.search_db('Contacts').item()


@pytest.fixture(scope='session')
def root_page(notion: Session):
    """Return the page reference used as parent page for live testing"""
    return notion.search_page('Tests', exact=True).item()


@pytest.fixture
def article_db(notion: Session, root_page: Page):
    """Simple database of articles"""

    class Article(schema.PageSchema, db_title='Articles'):
        name = schema.Column('Name', schema.Title())
        cost = schema.Column('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Column('Description', schema.Text())

    db = notion.create_db(parent=root_page, schema=Article)
    yield db
    db.delete()


@pytest.fixture(scope='session')
def page_hierarchy(notion: Session, root_page: Page):
    """Simple hierarchy of 3 pages nested in eachother: root -> l1 -> l2"""
    l1_page = notion.create_page(parent=root_page, title='level_1')
    l2_page = notion.create_page(parent=l1_page, title='level_2')
    yield root_page, l1_page, l2_page
    l2_page.delete()
    l1_page.delete()


@pytest.fixture(scope='session')
def all_cols_db(notion: Session):
    """Return manually created database with all columns, also AI columns"""
    return notion.search_db(ALL_COL_DB).item()


@pytest.fixture(scope='session')
def wiki_db(notion: Session):
    """Return manually created wiki db"""
    return notion.search_db(WIKI_DB).item()


# ToDo: Activate me later!
# @pytest.fixture(scope="session", autouse=True)
# def test_cleanups(notion: Session, root_page: Page, all_cols_db: Database, wiki_db: Database):
#     """Delete all databases and pages in the root_page before we start except of some special dbs and their content"""
#     for db in notion.search_db():
#         if db.parents[0] == root_page and db not in (all_cols_db, wiki_db):
#             db.delete()
#     for page in notion.search_page():
#         if page.parents and page.parents[0] == root_page and page.database not in (all_cols_db, wiki_db):
#             page.delete()

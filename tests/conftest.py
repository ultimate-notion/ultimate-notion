"""Fixtures for Ultimate-Notion unit tests.

Set `NOTION_TOKEN` environment variable for tests interacting with the Notion API.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import TypeAlias, TypeVar

import pytest

import ultimate_notion
from ultimate_notion import Session, schema
from ultimate_notion.database import Database
from ultimate_notion.page import Page
from ultimate_notion.session import ENV_NOTION_TOKEN

ALL_COL_DB = 'All Columns DB'  # Manually created DB in Notion with all possible columns including AI columns!
WIKI_DB = 'Wiki DB'
CONTACTS_DB = 'Contacts DB'
GETTING_STARTED_PAGE = 'Getting Started'

T = TypeVar('T')
Yield: TypeAlias = Generator[T, None, None]


# ToDo: See if we still need pytest-vcr
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
def notion() -> Yield[Session]:
    """Return the notion session used for live testing.

    This fixture depends on the `NOTION_TOKEN` environment variable. If it is not
    present, this fixture will skip the current test.
    """
    if os.getenv(ENV_NOTION_TOKEN) is None:
        msg = f'{ENV_NOTION_TOKEN} not defined! Use `export {ENV_NOTION_TOKEN}=secret_...`'
        raise RuntimeError(msg)

    with ultimate_notion.Session() as notion:
        yield notion


@pytest.fixture(scope='session')
def contacts_db(notion: Session) -> Database:
    """Return a test database"""
    return notion.search_db(CONTACTS_DB).item()


@pytest.fixture(scope='session')
def root_page(notion: Session) -> Page:
    """Return the page reference used as parent page for live testing"""
    return notion.search_page('Tests').item()


@pytest.fixture
def article_db(notion: Session, root_page: Page) -> Yield[Database]:
    """Simple database of articles"""

    class Article(schema.PageSchema, db_title='Articles'):
        name = schema.Column('Name', schema.Title())
        cost = schema.Column('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Column('Description', schema.Text())

    db = notion.create_db(parent=root_page, schema=Article)
    yield db
    db.delete()


@pytest.fixture(scope='session')
def page_hierarchy(notion: Session, root_page: Page) -> Yield[tuple[Page, Page, Page]]:
    """Simple hierarchy of 3 pages nested in eachother: root -> l1 -> l2"""
    l1_page = notion.create_page(parent=root_page, title='level_1')
    l2_page = notion.create_page(parent=l1_page, title='level_2')
    yield root_page, l1_page, l2_page
    l2_page.delete()
    l1_page.delete()


@pytest.fixture(scope='session')
def intro_page(notion: Session) -> Page:
    """Return the default 'Getting Started' page"""
    return notion.search_page(GETTING_STARTED_PAGE).item()


@pytest.fixture(scope='session')
def all_cols_db(notion: Session) -> Database:
    """Return manually created database with all columns, also AI columns"""
    return notion.search_db(ALL_COL_DB).item()


@pytest.fixture(scope='session')
def wiki_db(notion: Session) -> Database:
    """Return manually created wiki db"""
    return notion.search_db(WIKI_DB).item()


@pytest.fixture(scope='session')
def static_pages(root_page: Page, intro_page: Page) -> set[Page]:
    """Return all static pages for the unit tests"""
    return {intro_page, root_page}


@pytest.fixture(scope='session')
def static_dbs(all_cols_db: Database, wiki_db: Database, contacts_db: Database) -> set[Database]:
    """Return all static pages for the unit tests"""
    return {all_cols_db, wiki_db, contacts_db}


@pytest.fixture(scope='session', autouse=True)
def test_cleanups(notion: Session, root_page: Page, static_pages: set[Page], static_dbs: set[Database]):
    """Delete all databases and pages in the root_page before we start except of some special dbs and their content"""
    for db in notion.search_db():
        if db.parents[0] == root_page and db not in static_dbs:
            db.delete()
    for page in notion.search_page():
        if page in static_pages:
            continue
        if page.parents and page.parents[0] == root_page and page.database not in static_dbs:
            page.delete()

"""Fixtures for Ultimate-Notion unit tests.

Set `NOTION_TOKEN` environment variable for tests interacting with the Notion API.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import TypeAlias, TypeVar

import pytest

import ultimate_notion as uno
from ultimate_notion import Option, Session, schema
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

    with uno.Session() as notion:
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


@pytest.fixture
def task_db(notion: Session) -> Yield[Database]:
    status_options = [
        Option('Backlog', color=uno.Color.GRAY),
        Option('In Progres', color=uno.Color.BLUE),
        Option('Blocked', color=uno.Color.RED),
        Option('Done', color=uno.Color.GREEN),
        Option('Rejected', color=uno.Color.BROWN),
    ]
    priority_options = [
        Option('✹ High', color=uno.Color.RED),
        Option('✷ Medium', color=uno.Color.YELLOW),
        Option('✶ Low', color=uno.Color.GRAY),
    ]
    repeats_options = [
        Option('Daily', color=uno.Color.GRAY),
        Option('Weekly', color=uno.Color.PINK),
        Option('Bi-weekly', color=uno.Color.BROWN),
        Option('Monthly', color=uno.Color.ORANGE),
        Option('Bi-monthly', color=uno.Color.YELLOW),
        Option('Tri-monthly', color=uno.Color.GREEN),
        Option('Quarterly', color=uno.Color.BLUE),
        Option('Bi-annually', color=uno.Color.PURPLE),
        Option('Yearly', color=uno.Color.RED),
    ]
    urgency_formula = (
        'if(prop("Done"), "✅ Done", (if(empty(prop("Due Date")), "", '
        '(if((formatDate(now(), "YWD") == formatDate(prop("Due by"), "YWD")), "🔹 Today", '
        '(if((now() > prop("Due by")), ("🔥 " + prop("Time Left")), '
        '("🕐 " + prop("Time Left")))))))))'
    )
    due_formula = (
        'if(or(prop("Due Date") >= dateSubtract(dateSubtract(now(), hour(now()), "hours"), minute(now()), "minutes"), '
        'empty(prop("Repeats"))), prop("Due Date"), (if((prop("Repeats") == "Daily"), '
        'dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"), '
        'hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), 1, "days"), '
        'dateBetween(now(), dateAdd(dateSubtract(dateSubtract(prop("Due Date"), hour(prop("Due Date")), "hours"), '
        'minute(prop("Due Date")), "minutes"), 1, "days"), "days") + 1, "days"), 1, "days"), '
        'hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), (if((prop("Repeats") == "Weekly"), '
        'dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"), '
        'hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), 1, "days"), '
        'dateBetween(now(), dateAdd(dateSubtract(dateSubtract(prop("Due Date"), hour(prop("Due Date")), "hours"), '
        'minute(prop("Due Date")), "minutes"), 1, "days"), "weeks") + 1, "weeks"), 1, "days"), '
        'hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), '
        '(if((prop("Repeats") == "Bi-weekly"), dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract('
        'dateSubtract(prop("Due Date"), hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), 1, '
        '"days"), (dateBetween(now(), dateAdd(dateSubtract(dateSubtract(prop("Due Date"), hour(prop("Due Date")), '
        '"hours"), minute(prop("Due Date")), "minutes"), 1, "days"), "weeks") - (dateBetween(now(), '
        'dateAdd(dateSubtract(dateSubtract(prop("Due Date"), hour(prop("Due Date")), "hours"), '
        'minute(prop("Due Date")), "minutes"), 1, "days"), "weeks") % 2)) + 2, "weeks"), 1, "days"), '
        'hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), (if((prop("Repeats") == "Monthly"), '
        'dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"), '
        'hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), 1, "days"), dateBetween(now(), '
        'dateAdd(dateSubtract(dateSubtract(prop("Due Date"), hour(prop("Due Date")), "hours"), '
        'minute(prop("Due Date")), "minutes"), 1, "days"), "months") + 1, "months"), 1, "days"), '
        'hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), '
        '(if((prop("Repeats") == "Bi-monthly"), dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract('
        'dateSubtract(prop("Due Date"), hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), 1, '
        '"days"), (dateBetween(now(), dateAdd(dateSubtract(dateSubtract(prop("Due Date"), hour(prop("Due Date")), '
        '"hours"), minute(prop("Due Date")), "minutes"), 1, "days"), "months") - (dateBetween(now(), '
        'prop("Due Date"), "months") % 2)) + 2, "months"), 1, "days"), hour(prop("Due Date")), "hours"), '
        'minute(prop("Due Date")), "minutes"), (if((prop("Repeats") == "Tri-monthly"), dateAdd(dateAdd(dateSubtract('
        'dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"), hour(prop("Due Date")), "hours"), '
        'minute(prop("Due Date")), "minutes"), 1, "days"), (dateBetween(now(), dateAdd(dateSubtract(dateSubtract('
        'prop("Due Date"), hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), 1, "days"), '
        '"months") - (dateBetween(now(), prop("Due Date"), "months") % 3)) + 3, "months"), 1, "days"), '
        'hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), (if((prop("Repeats") == '
        '"Quarterly"), dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"), '
        'hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), 1, "days"), (dateBetween(now(), '
        'dateAdd(dateSubtract(dateSubtract(prop("Due Date"), hour(prop("Due Date")), "hours"), minute('
        'prop("Due Date")), "minutes"), 1, "days"), "months") - (dateBetween(now(), prop("Due Date"), "months") % 4)) '
        '+ 4, "months"), 1, "days"), hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), '
        '(if((prop("Repeats") == "Bi-annually"), dateSubtract(dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd('
        'dateSubtract(dateSubtract(prop("Due Date"), hour(prop("Due Date")), "hours"), minute(prop("Due Date")), '
        '"minutes"), 1, "days"), (dateBetween(now(), dateAdd(dateSubtract(dateSubtract(prop("Due Date"), '
        'hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), 1, "days"), "months") - '
        '(dateBetween(now(), prop("Due Date"), "months") % 6)) + 6, "months"), 1, "months"), hour(prop("Due Date")), '
        '"hours"), minute(prop("Due Date")), "minutes"), 1, "days"), (if((prop("Repeats") == "Yearly"), dateAdd('
        'dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"), hour(prop("Due Date")), '
        '"hours"), minute(prop("Due Date")), "minutes"), 1, "days"), dateBetween(now(), dateAdd(dateSubtract('
        'dateSubtract(prop("Due Date"), hour(prop("Due Date")), "hours"), minute(prop("Due Date")), "minutes"), 1, '
        '"days"), "years") + 1, "years"), 1, "days"), hour(prop("Due Date")), "hours"), minute(prop("Due Date")), '
        '"minutes"), fromTimestamp(toNumber("")))))))))))))))))))))'
    )
    w_left_formula = '(if((prop("Days Left") < 0), -1, 1)) * floor(abs(prop("Days Left") / 7))'
    d_left_formula = (
        'if(empty(prop("Due by")), toNumber(""), '
        '(if((prop("Due by") > now()), (dateBetween(prop("Due by"), now(), "days") + 1), '
        'dateBetween(prop("Due by"), now(), "days"))))'
    )
    t_left_formula = (
        'if(empty(prop("Days Left")), "", (((if((prop("Days Left") < 0), "-", "")) + '
        '(if((prop("Weeks Left") == 0), "", (format(abs(prop("Weeks Left"))) + "w")))) + '
        '(if(((prop("Days Left") % 7) == 0), "", (format(abs(prop("Days Left")) % 7) + "d")))))'
    )

    class Tasklist(schema.PageSchema, db_title='My Tasks'):
        """My personal task list"""

        task = schema.Column('Task', schema.Title())
        status = schema.Column('Status', schema.Select(status_options))
        priority = schema.Column('Priority', schema.Select(priority_options))
        urgency = schema.Column('Urgency', schema.Formula(urgency_formula))
        started = schema.Column('Started', schema.Date())
        due = schema.Column('Due by', schema.Formula(due_formula))
        done = schema.Column('Done', schema.Formula('prop("Status") == "Done"'))
        repeats = schema.Column('Repeats', schema.Select(repeats_options))
        w_left = schema.Column('Weeks Left', schema.Formula(w_left_formula))
        d_left = schema.Column('Days Left', schema.Formula(d_left_formula))
        t_left = schema.Column('Time Left', schema.Formula(t_left_formula))
        url = schema.Column('URL', schema.URL())
        parent = schema.Column('Parent Task', schema.Relation(schema.SelfRef))
        subs = schema.Column('Sub-Tasks', schema.Relation(schema.SelfRef, two_way_prop=parent))

    db = notion.create_db(parent=root_page, schema=Tasklist)
    yield db
    db.delete()


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

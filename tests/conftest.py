"""Fixtures for Ultimate-Notion unit tests.

Set `NOTION_TOKEN` environment variable for tests interacting with the Notion API.

Common pitfalls:
* never use dynamic values, e.g. datetime.now() in tests as VCRpy will record them and they will be used in the replay.
* be extremely careful with module/session level fixtures that use VCRpy. Only the first test using the fixture will
  record the cassette. All other tests will replay the same cassette, even if they use a different fixture. This can
  lead to unexpected results when not applied with extreme caution.
* be aware of the difference between `yield` and `return` in fixtures because the latter closes the cassette.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import TypeAlias, TypeVar
from unittest.mock import MagicMock, patch

import pytest
from _pytest.fixtures import SubRequest
from vcr import VCR
from vcr import mode as vcr_mode

import ultimate_notion as uno
from ultimate_notion import Option, Session, schema
from ultimate_notion.config import ENV_ULTIMATE_NOTION_CFG, get_cfg_file
from ultimate_notion.database import Database
from ultimate_notion.page import Page

ALL_COL_DB = 'All Columns DB'  # Manually created DB in Notion with all possible columns including AI columns!
WIKI_DB = 'Wiki DB'
CONTACTS_DB = 'Contacts DB'
GETTING_STARTED_PAGE = 'Getting Started'
TASK_DB = 'Task DB'

T = TypeVar('T')
Yield: TypeAlias = Generator[T, None, None]


@pytest.fixture(scope='module')
def vcr_config():
    """Configure pytest-recording."""
    secret_params = [
        'client_id',
        'client_secret',
        'access_token',
        'refresh_token',
        'code',
        'cookie',
        'authorization',
        'CF-RAY',
        'Date',
        'ETag',
        'X-Notion-Request-Id',
        'user-agent',
    ]

    def remove_secrets(response: dict[str, dict[str, str]]):
        for secret in secret_params:
            response['headers'].pop(secret, None)
        if 'body' in response and 'string' in response['body']:
            try:
                # remove secret tokens from body in Google API calls
                dct = json.loads(response['body']['string'])
                for secret in secret_params:
                    if secret in dct:
                        dct[secret] = 'secret...'
                response['body']['string'] = json.dumps(dct)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        return response

    return {
        'filter_headers': [(param, 'secret...') for param in secret_params],
        'filter_query_parameters': secret_params,
        'filter_post_data_parameters': secret_params,
        'before_record_response': remove_secrets,
    }


@pytest.fixture(scope='module')
def my_vcr(vcr_config: dict[str, str], request: SubRequest) -> VCR:
    """My VCR for module/session-level fixtures"""
    cassette_str = str(Path(request.module.__file__).parent / 'cassettes' / 'fixtures')
    cfg = vcr_config | {'cassette_library_dir': cassette_str}
    disable_recording = request.config.getoption('--disable-recording')
    if disable_recording:
        my_vcr = MagicMock()
        my_vcr.use_cassette.return_value.__enter__.return_value = None
    else:
        mode = request.config.getoption('--record-mode')
        if mode == 'rewrite':
            mode = 'all'
        my_vcr = VCR(record_mode=vcr_mode(mode), **cfg)
    return my_vcr


@pytest.fixture(scope='module')
def custom_config(my_vcr: VCR) -> Yield[Path]:
    # Create a temporary file
    if my_vcr.record_mode != vcr_mode.NONE:
        yield get_cfg_file()
    else:
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            cfg_path = tmp_dir_path / Path('config.cfg')

            with patch.dict(os.environ, {ENV_ULTIMATE_NOTION_CFG: str(cfg_path)}):
                client_secret_path = tmp_dir_path / Path('client_secret.json')
                client_secret_path.write_text(
                    '{"installed":{"client_id":"secret...","project_id":"ultimate-notion",'
                    '"auth_uri":"https://accounts.google.com/o/oauth2/auth",'
                    '"token_uri":"https://oauth2.googleapis.com/token",'
                    '"auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",'
                    '"client_secret":"secret...",'
                    '"redirect_uris":["http://localhost"]}}'
                )
                token_path = tmp_dir_path / Path('token.json')
                token_path.write_text(
                    '{"token": "secret...", "refresh_token": "secret...", "token_uri": "https://oauth2.googleapis.com/token",'
                    '"client_id": "secret.apps.googleusercontent.com", "client_secret": "secret...",'
                    '"scopes": ["https://www.googleapis.com/auth/tasks"], "universe_domain": "googleapis.com", '
                    '"expiry": "2099-01-04T17:33:08.600154Z"}'
                )
                yield cfg_path


@pytest.fixture(scope='module')
def notion() -> Yield[Session]:
    """Return the notion session used for live testing.

    This fixture depends on the `NOTION_TOKEN` environment variable. If it is not
    present, this fixture will skip the current test.
    """
    with uno.Session() as notion:
        yield notion


@pytest.fixture(scope='module')
def contacts_db(notion: Session, my_vcr: VCR) -> Database:
    """Return a test database"""
    with my_vcr.use_cassette('contacts_db.yaml'):
        return notion.search_db(CONTACTS_DB).item()


@pytest.fixture(scope='module')
def root_page(notion: Session, my_vcr: VCR) -> Page:
    """Return the page reference used as parent page for live testing"""
    with my_vcr.use_cassette('root_page.yaml'):
        return notion.search_page('Tests').item()


@pytest.fixture(scope='module')
def article_db(notion: Session, root_page: Page, my_vcr: VCR) -> Database:
    """Simple database of articles"""

    class Article(schema.PageSchema, db_title='Articles'):
        name = schema.Column('Name', schema.Title())
        cost = schema.Column('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Column('Description', schema.Text())

    with my_vcr.use_cassette('article_db.yaml'):
        return notion.create_db(parent=root_page, schema=Article)


@pytest.fixture(scope='module')
def page_hierarchy(notion: Session, root_page: Page, my_vcr: VCR) -> tuple[Page, Page, Page]:
    """Simple hierarchy of 3 pages nested in eachother: root -> l1 -> l2"""
    with my_vcr.use_cassette('page_hierarchy.yaml'):
        l1_page = notion.create_page(parent=root_page, title='level_1')
        l2_page = notion.create_page(parent=l1_page, title='level_2')
        return root_page, l1_page, l2_page


@pytest.fixture(scope='module')
def intro_page(notion: Session, my_vcr: VCR) -> Page:
    """Return the default 'Getting Started' page"""
    with my_vcr.use_cassette('intro_page.yaml'):
        return notion.search_page(GETTING_STARTED_PAGE).item()


@pytest.fixture(scope='module')
def all_cols_db(notion: Session, my_vcr: VCR) -> Database:
    """Return manually created database with all columns, also AI columns"""
    with my_vcr.use_cassette('all_cols_db.yaml'):
        return notion.search_db(ALL_COL_DB).item()


@pytest.fixture(scope='module')
def wiki_db(notion: Session, my_vcr: VCR) -> Database:
    """Return manually created wiki db"""
    with my_vcr.use_cassette('wiki_db.yaml'):
        return notion.search_db(WIKI_DB).item()


@pytest.fixture(scope='module')
def static_pages(root_page: Page, intro_page: Page, my_vcr: VCR) -> set[Page]:
    """Return all static pages for the unit tests"""
    with my_vcr.use_cassette('static_pages.yaml'):
        return {intro_page, root_page}


@pytest.fixture(scope='module')
def task_db(notion: Session, my_vcr: VCR) -> Database:
    """Return manually created wiki db"""
    with my_vcr.use_cassette('task_db.yaml'):
        return notion.search_db(TASK_DB).item()


@pytest.fixture(scope='module')
def static_dbs(
    all_cols_db: Database, wiki_db: Database, contacts_db: Database, task_db: Database, my_vcr: VCR
) -> set[Database]:
    """Return all static pages for the unit tests"""
    with my_vcr.use_cassette('static_dbs.yaml'):
        return {all_cols_db, wiki_db, contacts_db, task_db}


@pytest.fixture(scope='module')
def new_task_db(notion: Session, root_page: Page, my_vcr: VCR) -> Yield[Database]:
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
    done_formula = 'prop("Status") == "Done"'
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
    d_left_formula = (
        f'if(empty(({due_formula})), toNumber(""), '
        f'(if((({due_formula}) > now()), (dateBetween(({due_formula}), now(), "days") + 1), '
        f'dateBetween(({due_formula}), now(), "days"))))'
    )
    w_left_formula = f'(if((({d_left_formula}) < 0), -1, 1)) * floor(abs(({d_left_formula}) / 7))'
    t_left_formula = (
        f'if(empty(({d_left_formula})), "", (((if((({d_left_formula}) < 0), "-", "")) + '
        f'(if((({w_left_formula}) == 0), "", (format(abs(({w_left_formula}))) + "w")))) + '
        f'(if(((({d_left_formula}) % 7) == 0), "", (format(abs(({d_left_formula})) % 7) + "d")))))'
    )
    urgency_formula = (
        f'if(({done_formula}), "✅ Done", (if(empty(prop("Due Date")), "", '
        f'(if((formatDate(now(), "YWD") == formatDate(({due_formula}), "YWD")), "🔹 Today", '
        f'(if((now() > ({due_formula})), ("🔥 " + ({t_left_formula})), '
        f'("🕐 " + ({t_left_formula})))))))))'
    )

    class Tasklist(schema.PageSchema, db_title='My Tasks'):
        """My personal task list"""

        task = schema.Column('Task', schema.Title())
        status = schema.Column('Status', schema.Select(status_options))
        priority = schema.Column('Priority', schema.Select(priority_options))
        urgency = schema.Column('Urgency', schema.Formula(urgency_formula))
        started = schema.Column('Started', schema.Date())
        due_date = schema.Column('Due Date', schema.Date())
        due_by = schema.Column('Due by', schema.Formula(due_formula))
        done = schema.Column('Done', schema.Formula(done_formula))
        repeats = schema.Column('Repeats', schema.Select(repeats_options))
        url = schema.Column('URL', schema.URL())
        # ToDo: Reintroduce after the problem with adding a two-way relation column is fixed in the Notion API
        # parent = schema.Column('Parent Task', schema.Relation(schema.SelfRef))
        # subs = schema.Column('Sub-Tasks', schema.Relation(schema.SelfRef, two_way_col=parent))

    with my_vcr.use_cassette('new_task_db.yaml'):
        db = notion.create_db(parent=root_page, schema=Tasklist)
        yield db
        db.delete()


@pytest.fixture(scope='module', autouse=True)
def notion_cleanups(notion: Session, root_page: Page, static_pages: set[Page], static_dbs: set[Database], my_vcr: VCR):
    """Delete all databases and pages in the root_page after we ran except of some special dbs and their content.

    Be careful! This fixture opens a Notion session, which might lead to problems if you run it in parallel with other.
    Overwrite it in a a test module to avoid this behavior.
    """

    def clean():
        for db in notion.search_db():
            if db.ancestors[0] == root_page and db not in static_dbs:
                db.delete()
        for page in notion.search_page():
            if page in static_pages:
                continue
            ancestors = page.ancestors
            if (
                ancestors
                and ancestors[0] == root_page
                and page.database not in static_dbs
                and not any(p.is_deleted for p in ancestors)  # skip if any ancestor was already deleted
            ):
                page.delete()

    with my_vcr.use_cassette('notion_cleanups.yaml'):
        clean()

    yield

    with my_vcr.use_cassette('notion_cleanups.yaml'):
        clean()

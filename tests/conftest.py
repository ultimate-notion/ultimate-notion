"""Fixtures for Ultimate-Notion unit tests.

Set `NOTION_TOKEN` environment variable for tests interacting with the Notion API.

Most Notion API related fixtures have scope `module`, not `session` to avoid opening several sessions at one
in `test_exmples.py`.

Common pitfalls:
* never use dynamic values, e.g. datetime.now() in tests as VCRpy will record them and they will be used in the replay.
* be extremely careful with module/session level fixtures that use VCRpy. Only the first test using the fixture will
  record the cassette. All other tests will replay the same cassette, even if they use a different fixture. This can
  lead to unexpected results when not applied with extreme caution.
* be aware of the difference between `yield` and `return` in fixtures because the latter closes the cassette.
* In case of errors like `Token has been expired or revoked.` delete the token.json file in the `config.toml`
  directory. This will force the Google API to create a new token. Execute the tests and add `-s` to the pytest,
  e.g.: `hatch run vcr-rewrite -k test_sync_google_tasks -s`. Then check it using `hatch run vcr-only`.
  Be aware that `pytest-dotenv` will load the local `config.toml` file for development.
* Fixture that create new databases or objects should have function scope to avoid side effects between tests.
"""

from __future__ import annotations

import inspect
import json
import os
import tempfile
from collections.abc import Generator
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias, TypeVar
from unittest.mock import MagicMock, patch

import pytest
from _pytest.fixtures import SubRequest
from vcr import VCR
from vcr import mode as vcr_mode

import ultimate_notion as uno
from ultimate_notion import Option, Session, schema
from ultimate_notion.adapters.google.tasks import GTasksClient
from ultimate_notion.config import ENV_ULTIMATE_NOTION_CFG, get_cfg_file, get_or_create_cfg
from ultimate_notion.database import Database
from ultimate_notion.page import Page

if TYPE_CHECKING:
    from _pytest.config.argparsing import Parser

ALL_COL_DB = 'All Columns DB'  # Manually created DB in Notion with all possible columns including AI columns!
WIKI_DB = 'Wiki DB'
CONTACTS_DB = 'Contacts DB'
GETTING_STARTED_PAGE = 'Getting Started'
MD_TEXT_TEST_PAGE = 'Markdown Text Test'
MD_PAGE_TEST_PAGE = 'Markdown Page Test'
MD_SUBPAGE_TEST_PAGE = 'Markdown SubPage Test'
TASK_DB = 'Task DB'

T = TypeVar('T')
Yield: TypeAlias = Generator[T, None, None]


def pytest_addoption(parser: Parser):
    """Add falg to the pytest command line so that we can overwrite fixtures but not always!"""
    parser.addoption('--overwrite-fixtures', action='store_true', default=False, help='Overwrite existing fixtures.')


@pytest.fixture(scope='session')
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


@pytest.fixture(scope='session')
def custom_config(request: SubRequest) -> Yield[Path]:
    if request.config.getoption('--record-mode') is None:  # corresponds to VCR-ONLY
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            cfg_path = tmp_dir_path / Path('config.cfg')

            with patch.dict(os.environ, {ENV_ULTIMATE_NOTION_CFG: str(cfg_path)}):
                get_or_create_cfg()
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
    else:
        # Note: pytest-dotenv will use ~/.vscode/.env as default and load the local
        # ultimate-notion configuration file for development here.
        cfg_path = get_cfg_file()
        with patch.dict(os.environ, {ENV_ULTIMATE_NOTION_CFG: str(cfg_path)}):
            yield cfg_path


def vcr_fixture(scope: str, *, autouse: bool = False):
    """Return a VCR fixture for module/session-level fixtures"""
    if scope not in {'module', 'session'}:
        msg = f'Use this only for module or session scope, not {scope}!'
        raise ValueError(msg)

    def decorator(func):
        args = inspect.signature(func).parameters  # to inject the fixtures into the wrapper
        is_generator = inspect.isgeneratorfunction(func)

        def setup_vcr(request: SubRequest, vcr_config: dict[str, str]) -> tuple[VCR, str]:
            if scope == 'module':
                cassette_dir = str(Path(request.module.__file__).parent / 'cassettes' / 'fixtures')
                cassette_name = f'mod_{func.__name__}.yaml'  # same cassette for all modules!
            else:  # scope == 'session'
                cassette_dir = str(request.config.rootdir / 'tests' / 'cassettes' / 'fixtures')
                cassette_name = f'sess_{func.__name__}.yaml'

            vcr_config = vcr_config | {'cassette_library_dir': cassette_dir}
            disable_recording = request.config.getoption('--disable-recording')
            if disable_recording:
                vcr = MagicMock()
                vcr.use_cassette.return_value.__enter__.return_value = None
            else:
                mode = request.config.getoption('--record-mode')
                overwrite_fixtures = request.config.getoption('--overwrite-fixtures')
                if mode == 'rewrite':
                    # This avoids rewriting the fixture cassettes every time we rewrite for a new test!
                    mode = 'all' if overwrite_fixtures else 'once'
                elif mode is None:
                    mode = 'none'
                vcr = VCR(record_mode=vcr_mode(mode), **vcr_config)

            return vcr, cassette_name

        # Note: We added `notion` as fixture as py.test sometimes tears down the session fixture before the vcr fixture.
        # This should not happen as `getfixturevalue` defines the dependency but happens in some cases, thus this fix.

        @wraps(func)
        @pytest.fixture(scope=scope, autouse=autouse)
        def generator_wrapper(request: SubRequest, vcr_config: dict[str, str], notion: Session):
            vcr, cassette_name = setup_vcr(request, vcr_config)
            fixture_args = [request.getfixturevalue(arg) for arg in args]
            # This opens and closes the cassette for each iteration of the generator
            # and makes sure that only the fixture part of the generator is recorded.
            gen = func(*fixture_args)
            while True:
                try:
                    with vcr.use_cassette(cassette_name):
                        value = next(gen)
                    yield value
                except StopIteration as e:
                    if e.value is not None:
                        yield e.value
                    break

        @wraps(func)
        @pytest.fixture(scope=scope, autouse=autouse)
        def function_wrapper(request: SubRequest, vcr_config: dict[str, str], notion: Session):
            vcr, cassette_name = setup_vcr(request, vcr_config)
            fixture_args = [request.getfixturevalue(arg) for arg in args]

            with vcr.use_cassette(cassette_name):
                return func(*fixture_args)

        if is_generator:
            return generator_wrapper
        else:
            return function_wrapper

    return decorator


@pytest.fixture(scope='module')
def notion() -> Yield[Session]:
    """Return the notion session used for live testing."""
    with uno.Session() as notion:
        yield notion


@vcr_fixture(scope='module')
def contacts_db(notion: Session) -> Database:
    """Return a test database."""
    return notion.search_db(CONTACTS_DB).item()


@vcr_fixture(scope='module')
def root_page(notion: Session) -> Page:
    """Return the page reference used as parent page for live testing."""
    return notion.search_page('Tests').item()


@pytest.fixture(scope='function')
def article_db(notion: Session, root_page: Page) -> Yield[Database]:
    """Simple database of articles."""

    class Article(schema.PageSchema, db_title='Articles'):
        name = schema.Column('Name', schema.Title())
        cost = schema.Column('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Column('Description', schema.Text())

    db = notion.create_db(parent=root_page, schema=Article)
    yield db
    db.delete()


@pytest.fixture(scope='function')
def page_hierarchy(notion: Session, root_page: Page) -> Yield[tuple[Page, Page, Page]]:
    """Simple hierarchy of 3 pages nested in eachother: root -> l1 -> l2."""
    l1_page = notion.create_page(parent=root_page, title='level_1')
    l2_page = notion.create_page(parent=l1_page, title='level_2')
    yield root_page, l1_page, l2_page
    l2_page.delete(), l1_page.delete()


@vcr_fixture(scope='module')
def intro_page(notion: Session) -> Page:
    """Return the default 'Getting Started' page."""
    return notion.search_page(GETTING_STARTED_PAGE).item()


@vcr_fixture(scope='module')
def all_cols_db(notion: Session) -> Database:
    """Return manually created database with all columns, also AI columns."""
    return notion.search_db(ALL_COL_DB).item()


@vcr_fixture(scope='module')
def wiki_db(notion: Session) -> Database:
    """Return manually created wiki db."""
    return notion.search_db(WIKI_DB).item()


@vcr_fixture(scope='module')
def md_text_page(notion: Session) -> Page:
    """Return a page with markdown text content."""
    return notion.search_page(MD_TEXT_TEST_PAGE).item()


@vcr_fixture(scope='module')
def md_page(notion: Session) -> Page:
    """Return a page with markdown content."""
    return notion.search_page(MD_PAGE_TEST_PAGE).item()


@vcr_fixture(scope='module')
def md_subpage(notion: Session) -> Page:
    """Return a page with markdown content."""
    return notion.search_page(MD_SUBPAGE_TEST_PAGE).item()


@pytest.fixture(scope='module')
def static_pages(root_page: Page, intro_page: Page, md_text_page: Page, md_page: Page, md_subpage: Page) -> set[Page]:
    """Return all static pages for the unit tests."""
    return {intro_page, root_page, md_text_page, md_page, md_subpage}


@vcr_fixture(scope='module')
def task_db(notion: Session) -> Database:
    """Return manually created wiki db."""
    return notion.search_db(TASK_DB).item()


@vcr_fixture(scope='module')
def static_dbs(all_cols_db: Database, wiki_db: Database, contacts_db: Database, task_db: Database) -> set[Database]:
    """Return all static pages for the unit tests."""
    return {all_cols_db, wiki_db, contacts_db, task_db}


@pytest.fixture(scope='function')
def new_task_db(notion: Session, root_page: Page) -> Yield[Database]:
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

    db = notion.create_db(parent=root_page, schema=Tasklist)
    yield db
    db.delete()


@vcr_fixture(scope='module', autouse=True)
def notion_cleanups(notion: Session, root_page: Page, static_pages: set[Page], static_dbs: set[Database]):
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

    clean()
    yield
    clean()


def delete_all_taskslists():
    """Delete all taskslists except of the default one."""
    gtasks = GTasksClient(read_only=False)
    for tasklist in gtasks.all_tasklists():
        if not tasklist.is_default:
            tasklist.delete()

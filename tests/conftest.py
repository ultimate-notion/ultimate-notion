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
import logging
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pydantic
import pytest
from _pytest.fixtures import SubRequest
from google.auth.exceptions import RefreshError
from vcr import VCR
from vcr import mode as vcr_mode

import ultimate_notion as uno
from ultimate_notion import Database, Option, Page, Session, User, schema
from ultimate_notion import blocks as uno_blocks
from ultimate_notion.adapters.google.tasks import GTasksClient
from ultimate_notion.config import ENV_ULTIMATE_NOTION_CFG, ENV_ULTIMATE_NOTION_DEBUG, get_cfg_file, get_or_create_cfg
from ultimate_notion.utils import temp_attr, temp_timezone

if TYPE_CHECKING:
    from _pytest.config.argparsing import Parser

# Manually created DBs and Pages in Notion for testing purposes
TESTS_PAGE = 'Tests'  # root page for all tests with connected Notion integration
ALL_PROPS_DB = 'All Properties DB'  # DB with all possible properties including AI properties!
WIKI_DB = 'Wiki DB'
CONTACTS_DB = 'Contacts DB'
GETTING_STARTED_PAGE = 'Getting Started'
MD_TEXT_TEST_PAGE = 'Markdown Text Test'
MD_PAGE_TEST_PAGE = 'Markdown Test'
MD_SUBPAGE_TEST_PAGE = 'Markdown SubPage Test'
TASK_DB = 'Task DB'
EMBED_TEST_PAGE = 'Embed/Inline/Linked & Unfurl'
COMMENT_PAGE = 'Comments'
CUSTOM_EMOJI_PAGE = 'Custom Emoji Page'
FORMULA_DB = 'Formula DB'

# Original configuration file for the tests. The environment variables will be altered in some tests temporarily.
TEST_CFG_FILE = get_cfg_file()


def pytest_addoption(parser: Parser) -> None:
    """Add flag to the pytest command line so that we can overwrite fixtures but not always!"""
    parser.addoption(
        '--check-latest-release',
        action='store_true',
        default=False,
        help='Run tests that check the latest release on PyPI.',
    )
    parser.addoption(
        '--debug-uno',
        action='store_true',
        default=False,
        help='Enable DEBUG logging for Ultimate Notion.',
    )
    parser.addoption(
        '--file-upload',
        action='store_true',
        default=False,
        help='Run tests that upload files to Notion.',
    )


def pytest_exception_interact(node: pytest.Item, call: pytest.CallInfo, report: pytest.TestReport) -> None:
    """Handle exceptions raised in the tests and provide a bit more output for some exceptions."""
    exc_value = call.excinfo.value

    if isinstance(exc_value, pydantic.ValidationError):
        input_errors = '\n'.join(str(e['input']) for e in exc_value.errors())
        msg = f'Following erroneous inputs to the pydantic model {exc_value.title}:\n{input_errors}'
        logging.error(msg)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Define test selection based on command line flags."""
    # Handle check_latest_release marker
    marker_name = 'check_latest_release'
    flag_name = f'--{marker_name.replace("_", "-")}'
    if config.getoption(flag_name):
        release_tests = [item for item in items if marker_name in item.keywords]
        if not release_tests:
            pytest.skip(f'No tests with marker `{marker_name}` found!')
        items[:] = release_tests
    else:
        skip_release_test = pytest.mark.skip(reason=f'use flag `{flag_name}` to run')
        for item in items:
            if marker_name in item.keywords:
                item.add_marker(skip_release_test)

    # Handle file_upload marker - only if check_latest_release didn't already filter
    if not config.getoption('--check-latest-release'):
        file_upload_marker = 'file_upload'
        file_upload_flag = f'--{file_upload_marker.replace("_", "-")}'
        if not config.getoption(file_upload_flag):
            skip_file_upload = pytest.mark.skip(reason=f'use flag `{file_upload_flag}` to run file upload tests')
            for item in items:
                if file_upload_marker in item.keywords:
                    item.add_marker(skip_file_upload)


def exec_pyfile(file_path: str) -> None:
    """Executes a Python module as a script, as if it was called from the command line."""
    code = compile(Path(file_path).read_text(encoding='utf-8'), file_path, 'exec')
    exec(code, {'__MODULE__': '__main__'})  # noqa: S102


@pytest.fixture(scope='session', autouse=True)
def activate_debug_mode(request: SubRequest) -> None:
    """Activates debug mode if set accordingly in the config file"""
    if request.config.getoption('--debug-uno'):
        os.environ[ENV_ULTIMATE_NOTION_DEBUG] = '1'


@pytest.fixture(scope='session')
def vcr_config() -> dict[str, Any]:
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

    def remove_secrets(response: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
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
def custom_config(request: SubRequest) -> Iterator[Path]:
    """Return a custom configuration file for the tests.

    !!! note
        pytest-dotenv will use `../.vscode/.env` by default and load the local
        ultimate-notion configuration file defined in `.env`.
    """
    # compare with hatch scripts in `pyproject.toml`
    vcr_only = request.config.getoption('--record-mode') == 'none'
    test = request.config.getoption('--record-mode') == 'once' and not request.config.getoption('--disable-recording')

    if vcr_only:
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            cfg_path = tmp_dir_path / Path('config.toml')
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
                    '"expiry": "2099-01-04T17:33:08.600154Z"}'  # here we made sure that the token is valid forever
                )
                yield cfg_path

    elif test:
        cfg_path = get_cfg_file()
        # make sure that the token is valid forever to avoid problems with the Google API
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            shutil.copytree(cfg_path.parent, tmp_dir_path, dirs_exist_ok=True)
            cfg_path = tmp_dir_path / Path('config.toml')
            # make sure that the token is valid forever to avoid problems with the Google API in the tests using VCR
            with open(tmp_dir_path / Path('token.json'), 'r+', encoding='utf-8') as fh:
                token_data = json.load(fh)
                token_data['expiry'] = '2099-01-04T17:33:08.600154Z'
                fh.seek(0)
                json.dump(token_data, fh)
            with patch.dict(os.environ, {ENV_ULTIMATE_NOTION_CFG: str(cfg_path)}):
                yield cfg_path

    else:  # vcr-off and vcr-rewrite
        cfg_path = get_cfg_file()
        with patch.dict(os.environ, {ENV_ULTIMATE_NOTION_CFG: str(cfg_path)}):
            yield cfg_path


def vcr_fixture(scope: str, *, autouse: bool = False) -> Callable[..., Any]:
    """Return a VCR fixture for module/session-level fixtures"""
    if scope not in {'module', 'session'}:
        msg = f'Use this only for module or session scope, not {scope}!'
        raise ValueError(msg)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        args = inspect.signature(func).parameters  # to inject the fixtures into the wrapper
        is_generator = inspect.isgeneratorfunction(func)

        def setup_vcr(request: SubRequest, vcr_config: dict[str, str]) -> tuple[VCR | MagicMock, str]:
            if scope == 'module':
                cassette_dir = str(Path(request.module.__file__).parent / 'cassettes' / 'fixtures')
                cassette_name = f'mod_{func.__name__}.yaml'  # same cassette for all modules!
            else:  # scope == 'session'
                cassette_dir = str(request.config.rootdir / 'tests' / 'cassettes' / 'fixtures')
                cassette_name = f'sess_{func.__name__}.yaml'

            vcr_config = vcr_config.copy()  # to avoid changing the original config
            vcr_config |= {'cassette_library_dir': cassette_dir}
            disable_recording = request.config.getoption('--disable-recording')
            if disable_recording:
                vcr: MagicMock = MagicMock()
                vcr.use_cassette.return_value.__enter__.return_value = None
            else:
                mode = request.config.getoption('--record-mode')
                if mode == 'rewrite':
                    # This avoids rewriting the fixture cassettes every time we rewrite for a new test!
                    mode = 'new_episodes'
                elif mode is None:
                    mode = 'none'
                vcr = VCR(record_mode=vcr_mode(mode), **vcr_config)

            return vcr, cassette_name

        # Note: We added `notion` as fixture as py.test sometimes tears down the session fixture before the vcr fixture.
        # This should not happen as `getfixturevalue` defines the dependency but happens in some cases, thus this fix.

        @wraps(func)
        @pytest.fixture(scope=scope, autouse=autouse)
        def generator_wrapper(request: SubRequest, vcr_config: dict[str, str], notion_cached: Session) -> Iterator[Any]:
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
        def function_wrapper(request: SubRequest, vcr_config: dict[str, str], notion_cached: Session) -> Any:
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
def notion_cached() -> Iterator[Session]:
    """Return the notion session used for live testing."""
    with uno.Session() as notion:
        yield notion


@pytest.fixture(scope='function')
def notion(notion_cached: Session) -> Iterator[Session]:
    """Return a fresh notion session without state for testing."""
    with temp_attr(notion_cached, cache={}, _own_bot_id=None):
        yield notion_cached


@pytest.fixture(scope='module')
def person(notion_cached: Session) -> User:
    """Return a user object for testing."""
    return notion_cached.search_user('Florian Wilhelm').item()


@vcr_fixture(scope='module')
def contacts_db(notion_cached: Session) -> Database:
    """Return a test database."""
    return notion_cached.search_db(CONTACTS_DB).item()


@vcr_fixture(scope='module')
def root_page(notion_cached: Session) -> Page:
    """Return the page reference used as parent page for live testing."""
    return notion_cached.search_page(TESTS_PAGE).item()


@pytest.fixture(scope='function')
def article_db(notion_cached: Session, root_page: Page) -> Iterator[Database]:
    """Simple database of articles."""

    class Article(schema.Schema, db_title='Articles'):
        name = schema.Title('Name')
        cost = schema.Number('Cost', format=schema.NumberFormat.DOLLAR)
        desc = schema.Text('Description')

    db = notion_cached.create_db(parent=root_page, schema=Article)
    yield db
    db.delete()


@pytest.fixture(scope='function')
def page_hierarchy(notion_cached: Session, root_page: Page) -> Iterator[tuple[Page, Page, Page]]:
    """Simple hierarchy of 3 pages nested in eachother: root -> l1 -> l2."""
    l1_page = notion_cached.create_page(parent=root_page, title='level_1')
    l2_page = notion_cached.create_page(parent=l1_page, title='level_2')
    yield root_page, l1_page, l2_page
    l2_page.delete(), l1_page.delete()


@vcr_fixture(scope='module')
def intro_page(notion_cached: Session) -> Page:
    """Return the default 'Getting Started' page."""
    return notion_cached.search_page(GETTING_STARTED_PAGE).item()


@vcr_fixture(scope='module')
def all_props_db(notion_cached: Session) -> Database:
    """Return manually created database with all properties, also AI properties."""
    return notion_cached.search_db(ALL_PROPS_DB).item()


@vcr_fixture(scope='module')
def wiki_db(notion_cached: Session) -> Database:
    """Return manually created wiki db."""
    return notion_cached.search_db(WIKI_DB).item()


@vcr_fixture(scope='module')
def formula_db(notion_cached: Session) -> Database:
    """Return manually created formula db."""
    return notion_cached.search_db(FORMULA_DB).item()


@vcr_fixture(scope='module')
def md_text_page(notion_cached: Session) -> Page:
    """Return a page with markdown text content."""
    return notion_cached.search_page(MD_TEXT_TEST_PAGE).item()


@vcr_fixture(scope='module')
def md_page(notion_cached: Session) -> Page:
    """Return a page with markdown content."""
    return notion_cached.search_page(MD_PAGE_TEST_PAGE).item()


@vcr_fixture(scope='module')
def md_subpage(notion_cached: Session) -> Page:
    """Return a page with markdown content."""
    return notion_cached.search_page(MD_SUBPAGE_TEST_PAGE).item()


@vcr_fixture(scope='module')
def embed_page(notion_cached: Session) -> Page:
    """Return a page with embed/inline/linked & unfurl content."""
    return notion_cached.search_page(EMBED_TEST_PAGE).item()


@vcr_fixture(scope='module')
def comment_page(notion_cached: Session) -> Page:
    """Return a page with comments."""
    return notion_cached.search_page(COMMENT_PAGE).item()


@vcr_fixture(scope='module')
def custom_emoji_page(notion_cached: Session) -> Page:
    """Return a page with a custom emoji."""
    return notion_cached.search_page(CUSTOM_EMOJI_PAGE).item()


@pytest.fixture(scope='module')
def static_pages(  # noqa: PLR0917
    root_page: Page,
    intro_page: Page,
    md_text_page: Page,
    md_page: Page,
    md_subpage: Page,
    embed_page: Page,
    comment_page: Page,
    custom_emoji_page: Page,
) -> set[Page]:
    """Return all static pages for the unit tests."""
    return {
        intro_page,
        root_page,
        md_text_page,
        md_page,
        md_subpage,
        embed_page,
        comment_page,
        custom_emoji_page,
    }


@vcr_fixture(scope='module')
def task_db(notion_cached: Session) -> Database:
    """Return manually created wiki db."""
    return notion_cached.search_db(TASK_DB).item()


@vcr_fixture(scope='module')
def static_dbs(
    all_props_db: Database, wiki_db: Database, contacts_db: Database, task_db: Database, formula_db: Database
) -> set[Database]:
    """Return all static pages for the unit tests."""
    return {all_props_db, wiki_db, contacts_db, task_db, formula_db}


@pytest.fixture(scope='function')
def new_task_db(notion_cached: Session, root_page: Page) -> Iterator[Database]:
    status_options = [
        Option('Backlog', color=uno.Color.GRAY),
        Option('In Progress', color=uno.Color.BLUE),
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
        Option('Quarterly', color=uno.Color.BLUE),
        Option('Bi-annually', color=uno.Color.PURPLE),
        Option('Yearly', color=uno.Color.RED),
    ]
    done_formula = 'prop("Status") == "Done"'
    due_formula = (
        'if(or(prop("Due Date")>=dateSubtract(dateSubtract(now(),hour(now()),"hours"),minute(now()),"minutes"),'
        'empty(prop("Repeats"))),prop("Due Date"),'
        '(if((prop("Repeats")=="Daily"),'
        'dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),1,"days"),'
        'dateBetween(now(),dateAdd(dateSubtract(dateSubtract(prop("Due Date"),hour(prop("Due Date")),"hours"),'
        'minute(prop("Due Date")),"minutes"),1,"days"),"days")+1,"days"),1,"days"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),'
        '(if((prop("Repeats")=="Weekly"),'
        'dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),1,"days"),'
        'dateBetween(now(),dateAdd(dateSubtract(dateSubtract(prop("Due Date"),hour(prop("Due Date")),"hours"),'
        'minute(prop("Due Date")),"minutes"),1,"days"),"weeks")+1,"weeks"),1,"days"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),'
        '(if((prop("Repeats")=="Bi-weekly"),'
        'dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),1,"days"),'
        '(dateBetween(now(),dateAdd(dateSubtract(dateSubtract(prop("Due Date"),hour(prop("Due Date")),"hours"),'
        'minute(prop("Due Date")),"minutes"),1,"days"),"weeks")-'
        '(dateBetween(now(),dateAdd(dateSubtract(dateSubtract(prop("Due Date"),hour(prop("Due Date")),"hours"),'
        'minute(prop("Due Date")),"minutes"),1,"days"),"weeks")%2))+2,"weeks"),1,"days"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),'
        '(if((prop("Repeats")=="Monthly"),'
        'dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),1,"days"),'
        'dateBetween(now(),dateAdd(dateSubtract(dateSubtract(prop("Due Date"),hour(prop("Due Date")),"hours"),'
        'minute(prop("Due Date")),"minutes"),1,"days"),"months")+1,"months"),1,"days"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),'
        '(if((prop("Repeats")=="Quarterly"),'
        'dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),1,"days"),'
        '(dateBetween(now(),dateAdd(dateSubtract(dateSubtract(prop("Due Date"),hour(prop("Due Date")),"hours"),'
        'minute(prop("Due Date")),"minutes"),1,"days"),"months")-'
        '(dateBetween(now(),dateAdd(dateSubtract(dateSubtract(prop("Due Date"),hour(prop("Due Date")),"hours"),'
        'minute(prop("Due Date")),"minutes"),1,"days"),"months")%4))+4,"months"),1,"days"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),'
        '(if((prop("Repeats")=="Bi-annually"),'
        'dateSubtract(dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),1,"days"),'
        '(dateBetween(now(),dateAdd(dateSubtract(dateSubtract(prop("Due Date"),hour(prop("Due Date")),"hours"),'
        'minute(prop("Due Date")),"minutes"),1,"days"),"months")-'
        '(dateBetween(now(),dateAdd(dateSubtract(dateSubtract(prop("Due Date"),hour(prop("Due Date")),"hours"),'
        'minute(prop("Due Date")),"minutes"),1,"days"),"months")%6))+6,"months"),1,"months"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),1,"days"),'
        '(if((prop("Repeats")=="Yearly"),'
        'dateAdd(dateAdd(dateSubtract(dateAdd(dateAdd(dateSubtract(dateSubtract(prop("Due Date"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),1,"days"),'
        'dateBetween(now(),dateAdd(dateSubtract(dateSubtract(prop("Due Date"),hour(prop("Due Date")),"hours"),'
        'minute(prop("Due Date")),"minutes"),1,"days"),"years")+1,"years"),1,"days"),'
        'hour(prop("Due Date")),"hours"),minute(prop("Due Date")),"minutes"),'
        'fromTimestamp(toNumber("")))))))))))))))))'
    )
    urgency_formula = (
        f'if(({done_formula}), "✅ Done", '
        f'if(empty(prop("Due Date")), "", '
        f'if(now() > ({due_formula}), "🔥 Overdue", "🕐 Upcoming")))'
    )

    class Tasklist(schema.Schema, db_title='My Tasks'):
        """My personal task list"""

        task = schema.Title('Task')
        status = schema.Select('Status', options=status_options)
        priority = schema.Select('Priority', options=priority_options)
        urgency = schema.Formula('Urgency', formula=urgency_formula)
        started = schema.Date('Started')
        due_date = schema.Date('Due Date')
        due_by = schema.Formula('Due by', formula=due_formula)
        done = schema.Formula('Done', formula=done_formula)
        repeats = schema.Select('Repeats', options=repeats_options)
        url = schema.URL('URL')
        # ToDo: Reintroduce after the problem with adding a two-way relation property is fixed in the Notion API
        # parent = schema.Relation('Parent Task', schema.SelfRef)
        # subs = schema.Relation('Sub-Tasks', schema.SelfRef, two_way_prop=parent)

    db = notion_cached.create_db(parent=root_page, schema=Tasklist)
    yield db
    db.delete()


@vcr_fixture(scope='module', autouse=True)
def notion_cleanups(
    notion_cached: Session, root_page: Page, static_pages: set[Page], static_dbs: set[Database]
) -> Iterator[None]:
    """Delete all databases and pages in the root_page after we ran except of some special dbs and their content.

    Be careful! This fixture opens a Notion session, which might lead to problems if you run it in parallel with other.
    Overwrite it in a a test module to avoid this behavior.
    """

    def clean() -> None:
        for db in notion_cached.search_db():
            if db.ancestors[0] == root_page and db not in static_dbs:
                db.delete()
        for page in notion_cached.search_page():
            if page in static_pages:
                continue
            ancestors = page.ancestors
            if (
                ancestors
                and ancestors[0] == root_page
                and page.parent_db not in static_dbs
                # skip if any ancestor page or database was already deleted
                and not any(isinstance(p, Page | Database) and p.is_deleted for p in ancestors)
            ):
                page.delete()

    clean()
    yield
    clean()


def delete_all_taskslists() -> None:
    """Delete all taskslists except of the default one."""
    gtasks = GTasksClient(read_only=False)
    try:
        for tasklist in gtasks.all_tasklists():
            if not tasklist.is_default:
                tasklist.delete()
    except RefreshError as e:
        msg = (
            "We tampered with the token's expiry date to allow for VCR testing but you seem to try to "
            'connect to the Google API now.\n'
            f'Delete `{TEST_CFG_FILE.parent / "token.json"}` and run:\n'
            'hatch run vcr-off -k test_gtask_client\n'
            'to perform the authentication flow before rewriting the VCR cassettes.'
        )
        raise RuntimeError(msg) from e


@pytest.fixture(scope='function')
def tz_berlin() -> Iterator[str]:
    """Set the timezone to Berlin for the tests."""
    tz = 'Europe/Berlin'
    with temp_timezone(tz):
        yield tz


def assert_eventually(assertion_func: Callable[..., Any], retries: int = 5, delay: int = 3) -> None:
    """Retry the provided assertion function for a given number of attempts with a delay.

    Args:
        assertion_func: The lambda containing the assertion logic without parameters.
        retries: Number of retries before failing.
        delay: Delay in seconds between retries.
    """
    for attempt in range(retries):
        try:
            assertion_func()
            return
        except AssertionError:
            if attempt < retries - 1:
                time.sleep(delay)
    assertion_func()


@pytest.fixture(autouse=True)
def strict_api_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set very strict API limits to test appending blocks batch-wise."""
    monkeypatch.setattr(uno_blocks, 'MAX_BLOCK_CHILDREN', 5)
    monkeypatch.setattr(uno_blocks, 'MAX_BLOCKS_PER_REQUEST', 10)


def all_blocks() -> tuple[uno.Block, ...]:
    """Return a list of one instance of each block type."""
    img_url = uno.url('https://github.com/ultimate-notion/ultimate-notion/blob/main/docs/assets/images/favicon.png')
    blocks = [
        uno_blocks.TableOfContents(color=uno.Color.PINK),
        h1_block := uno_blocks.Heading1('Heading 1', toggleable=True),
        h2_block := uno_blocks.Heading2('Heading 2', toggleable=True),
        uno_blocks.Heading3('Heading 3'),
        uno_blocks.Paragraph('Paragraph'),
        b1_block := uno_blocks.BulletedItem('Bulleted List Item'),
        uno_blocks.Divider(),
        uno_blocks.Callout('Callout', icon='💡'),
        uno_blocks.Quote('Quote'),
        uno_blocks.ToDoItem('ToDo', checked=True),
        uno_blocks.NumberedItem('Numbered List Item'),
        uno_blocks.Equation('E=mc^2'),
        uno_blocks.Breadcrumb(),
        uno_blocks.Paragraph(uno.text('Google link', href='https://www.google.com')),
    ]
    h1_block.append(
        [
            uno_blocks.Code('print("Hello World!")', language='python'),
            uno_blocks.Paragraph('Code block above'),
        ]
    )
    h2_block.append(
        [
            uno_blocks.Image(img_url, caption='Ultimate Notion Logo'),
            uno_blocks.Paragraph('Image above'),
        ]
    )
    b1_block.append(
        [
            uno_blocks.BulletedItem('Nested numbered list item in bulleted list item'),
            table := uno_blocks.Table(2, 2),
        ]
    )
    table[0] = ('Header 1', 'Header 2')
    table[1] = ('Cell 1', 'Cell 2')
    return tuple(blocks)


@dataclass
class URL:
    """Container for test URLs."""

    img: str
    file: str
    video: str
    pdf: str
    audio: str

    @property
    def pdf_name(self) -> str:
        return self.pdf.rsplit('/').pop()

    @property
    def file_name(self) -> str:
        return self.file.rsplit('/').pop()


@pytest.fixture(scope='module')
def test_url() -> URL:
    """Return a set of URLs for testing."""
    return URL(
        img='https://cdn.pixabay.com/photo/2019/08/06/09/16/flowers-4387827_1280.jpg',
        file='https://www.google.de/robots.txt',
        video='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        pdf='https://www.rd.usda.gov/sites/default/files/pdf-sample_0.pdf',
        audio='https://samplelib.com/lib/preview/mp3/sample-3s.mp3',
    )

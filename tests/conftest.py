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

import contextlib
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
from random import randint
from typing import TYPE_CHECKING, Any, Literal, Protocol
from unittest.mock import MagicMock, patch

import pydantic
import pytest
from _pytest.fixtures import SubRequest
from google.auth.exceptions import RefreshError
from vcr import VCR  # type: ignore[import-untyped]
from vcr import mode as vcr_mode

import ultimate_notion as uno
from ultimate_notion import Database, NumberFormat, Option, Page, Session, User, schema
from ultimate_notion import blocks as uno_blocks
from ultimate_notion.adapters.google.tasks import GTasksClient
from ultimate_notion.config import (
    ENV_NOTION_TOKEN,
    ENV_ULTIMATE_NOTION_CFG,
    ENV_ULTIMATE_NOTION_DEBUG,
    get_cfg_file,
    get_or_create_cfg,
)
from ultimate_notion.utils import temp_attr, temp_timezone

if TYPE_CHECKING:
    from _pytest.config.argparsing import Parser

# Name of the environment variable that overrides the title of the root test page.
# This lets a maintainer point the suite at the root page they shared with their own
# integration without having to name it `Tests`. The default keeps the recorded
# cassettes (which searched for `Tests`) working unchanged.
ENV_TEST_ROOT_PAGE = 'UNO_TEST_ROOT_PAGE'

# Manually created DBs and Pages in Notion for testing purposes
TESTS_PAGE = os.environ.get(ENV_TEST_ROOT_PAGE, 'Tests')  # root page for all tests with connected Notion integration
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

# Mutually exclusive pytest markers, that are not run by default and enabled via command line flags
PYTEST_MARKERS = ['check_latest_release', 'file_upload']

# --- Workspace-portable cassettes (issue #292) --------------------------------------------------
# The default VCR matchers ignore request bodies, so every `POST /v1/search` matches by path alone
# and a cassette with several searches only replays them in the order they were recorded. That makes
# the shared fixtures fragile and ties a recording to the workspace it was made in. We add a matcher
# that *additionally* compares the JSON body of `/v1/search` requests (a no-op for every other
# endpoint), so each search is matched by what it actually queries. The same problem affects
# database/datasource `/query` requests, whose filter/sort criteria also live in the body (issue
# #367); a parallel matcher compares those by body too. We also scrub a non-default root
# page title back to the canonical `Tests` on record, so a maintainer who cannot name their shared
# root page `Tests` (via `UNO_TEST_ROOT_PAGE`) still produces cassettes that replay against the
# committed set. See the "Set up a Notion test workspace" section in `CONTRIBUTING.md`.

NOTION_SEARCH_PATH = '/v1/search'
# Database/datasource queries (`POST /v1/databases/{id}/query`, `POST /v1/data_sources/{id}/query`)
# carry their filter and sort criteria in the request body, which the default matchers ignore. We
# recognise them by the `/query` path suffix (the id in the path is already distinguished by the
# default `path` matcher). See issue #367.
NOTION_QUERY_PATH_SUFFIX = '/query'
VCR_DEFAULT_MATCHERS = ['method', 'scheme', 'host', 'port', 'path', 'query']
VCR_SEARCH_MATCHER = 'notion_search_body'
VCR_QUERY_MATCHER = 'notion_query_body'


def _request_json_body(request: Any) -> Any:
    """Return the parsed JSON body of a VCR request, or the raw body if it is not JSON."""
    body = request.body
    if isinstance(body, bytes):
        try:
            body = body.decode('utf-8')
        except UnicodeDecodeError:
            return body
    try:
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return body


def match_search_body(r1: Any, r2: Any) -> bool:
    """Match `POST /v1/search` requests by their JSON body; match everything else unconditionally.

    Combined with the default `path` matcher this adds body matching *only* for the search endpoint,
    leaving all other endpoints matched exactly as before.
    """
    if not (r1.path == NOTION_SEARCH_PATH and r2.path == NOTION_SEARCH_PATH):
        return True
    return bool(_request_json_body(r1) == _request_json_body(r2))


def match_query_body(r1: Any, r2: Any) -> bool:
    """Match `POST .../query` requests by their JSON body; match everything else unconditionally.

    Combined with the default `path` matcher this adds body matching *only* for the database/datasource
    query endpoint, leaving all other endpoints matched exactly as before.
    """
    if not (r1.path.endswith(NOTION_QUERY_PATH_SUFFIX) and r2.path.endswith(NOTION_QUERY_PATH_SUFFIX)):
        return True
    return bool(_request_json_body(r1) == _request_json_body(r2))


def register_notion_matchers(vcr: VCR) -> None:
    """Register Ultimate Notion's custom VCR matchers on a freshly built VCR instance."""
    vcr.register_matcher(VCR_SEARCH_MATCHER, match_search_body)
    vcr.register_matcher(VCR_QUERY_MATCHER, match_query_body)


def pytest_recording_configure(config: pytest.Config, vcr: VCR) -> None:
    """Register custom matchers on the VCR instance built by pytest-recording (`@pytest.mark.vcr`)."""
    register_notion_matchers(vcr)


# --- Workspace-portable cassettes: shared-id normalization (issue #296) --------------------------
# Matching searches by body (#292/#294) makes the *common* live test portable, but the shared
# workspace objects still carry ids that differ between workspaces: the root page, the seeded static
# pages/databases, the integration bot, the workspace members and the workspace itself. A test that
# asserts identity against such a fixture (`page.parent == root_page`, compared by id) or that puts a
# shared object's id in a request *path* (`GET /v1/blocks/{root_id}/children`) therefore cannot be
# recorded against one workspace and replayed against cassettes recorded in another.
#
# We normalise those ids to stable placeholders. Shared objects are recognised by their (stable)
# title, the integration bot and the workspace by the bot's own user object, and human members by the
# order in which they are first seen; every occurrence of their ids -- in request paths/bodies and in
# response bodies, in both dashed and dash-less form -- is rewritten to a fixed placeholder. Because
# VCR runs `before_record_request` over the outgoing request *before matching* as well as before
# recording (see `Cassette.play_response`), the very same normalisation is applied when matching, so
# recordings from different workspaces are interchangeable.
#
# VCR also runs `before_record_response` on playback, not only on recording. The committed cassettes
# were migrated to these placeholders once, so on replay the hooks re-see only placeholder ids: the
# registry never learns them again (it is idempotent -- see `PLACEHOLDER_IDS`), the request hook is an
# identity, and response normalisation is byte-preserving (it must not reflow JSON or desync
# `Content-Length`). See the "Add a new live (VCR) test" section in `CONTRIBUTING.md`.

# Placeholder ids are valid-shaped but obviously synthetic version-4 UUIDs. The all-zero id
# `00000000-0000-0000-0000-000000000000` (Ultimate Notion's "unset" sentinel) has a `0` version
# nibble, so these `...-4000-8000-...` placeholders never collide with it.
PLACEHOLDER_WORKSPACE = '00000000-0000-4000-8000-0000000000f0'
PLACEHOLDER_BOT = '00000000-0000-4000-8000-0000000000f1'
# Human members, assigned in first-seen order. Four is comfortably more than any test workspace uses.
PLACEHOLDER_PERSONS = (
    '00000000-0000-4000-8000-0000000000fa',
    '00000000-0000-4000-8000-0000000000fb',
    '00000000-0000-4000-8000-0000000000fc',
    '00000000-0000-4000-8000-0000000000fd',
)
# Shared pages/databases, keyed by their stable title (the root page uses the configured title so a
# workspace whose root is not named `Tests` still maps). Order/value is irrelevant as long as it is
# fixed: the migration of the committed cassettes used exactly this mapping.
SHARED_OBJECT_PLACEHOLDERS: dict[str, str] = {
    TESTS_PAGE: '00000000-0000-4000-8000-000000000001',
    GETTING_STARTED_PAGE: '00000000-0000-4000-8000-000000000002',
    MD_TEXT_TEST_PAGE: '00000000-0000-4000-8000-000000000003',
    MD_PAGE_TEST_PAGE: '00000000-0000-4000-8000-000000000004',
    MD_SUBPAGE_TEST_PAGE: '00000000-0000-4000-8000-000000000005',
    EMBED_TEST_PAGE: '00000000-0000-4000-8000-000000000006',
    COMMENT_PAGE: '00000000-0000-4000-8000-000000000007',
    CUSTOM_EMOJI_PAGE: '00000000-0000-4000-8000-000000000008',
    ALL_PROPS_DB: '00000000-0000-4000-8000-000000000009',
    WIKI_DB: '00000000-0000-4000-8000-00000000000a',
    CONTACTS_DB: '00000000-0000-4000-8000-00000000000b',
    TASK_DB: '00000000-0000-4000-8000-00000000000c',
    FORMULA_DB: '00000000-0000-4000-8000-00000000000d',
}
# The set of every placeholder value. `before_record_response` runs on playback too, so the registry
# re-learns from already-placeholder responses; ids that are already placeholders must never be learnt
# again (especially persons, assigned by first-seen order, which would otherwise be remapped onto a
# different placeholder and corrupt the replay). Learning is therefore idempotent.
PLACEHOLDER_IDS: frozenset[str] = frozenset(
    {PLACEHOLDER_WORKSPACE, PLACEHOLDER_BOT, *PLACEHOLDER_PERSONS, *SHARED_OBJECT_PLACEHOLDERS.values()}
)


def _undash(notion_id: str) -> str:
    """Return a Notion id without its dashes, as it appears in `notion.so/...` URLs."""
    return notion_id.replace('-', '')


def _object_title(obj: dict[str, Any]) -> str | None:
    """Return the plain-text title of a Notion page/database object, or `None` if it has none."""
    if obj.get('object') == 'database':
        title_rich_text = obj.get('title', [])
    elif obj.get('object') == 'page':
        title_prop = next((p for p in obj.get('properties', {}).values() if p.get('type') == 'title'), None)
        title_rich_text = title_prop.get('title', []) if title_prop else []
    else:
        return None
    title = ''.join(part.get('plain_text', '') for part in title_rich_text)
    return title or None


class _SharedIdRegistry:
    """Collects the recording workspace's shared-object ids and maps them to stable placeholders.

    Populated from recorded responses (`learn_from_response`) and consulted to rewrite every recorded
    request and response (`scrub`). One module-level instance is shared across the whole pytest session
    so an id discovered while recording one cassette is normalised in every later cassette too.
    """

    def __init__(self) -> None:
        # real (dashed) id -> placeholder (dashed)
        self._placeholders: dict[str, str] = {}
        self._persons_seen = 0

    def _add(self, real_id: str, placeholder: str) -> None:
        self._placeholders.setdefault(real_id, placeholder)

    def learn_from_response(self, body: Any) -> None:
        """Walk a parsed JSON response body and register any shared-object ids it reveals."""
        if isinstance(body, dict):
            obj_type = body.get('object')
            obj_id = body.get('id')
            # Ids that are already placeholders (e.g. when re-learning from a replayed cassette) must
            # not be learnt again, so normalisation is idempotent.
            if isinstance(obj_id, str) and obj_id not in PLACEHOLDER_IDS:
                if obj_type in {'page', 'database'}:
                    placeholder = SHARED_OBJECT_PLACEHOLDERS.get(_object_title(body) or '')
                    if placeholder is not None:
                        self._add(obj_id, placeholder)
                elif obj_type == 'user':
                    self._learn_user(body)
            for value in body.values():
                self.learn_from_response(value)
        elif isinstance(body, list):
            for value in body:
                self.learn_from_response(value)

    def _learn_user(self, user: dict[str, Any]) -> None:
        """Register the integration bot (and its workspace) or a human member from a full user object."""
        if user.get('type') == 'bot':
            self._add(user['id'], PLACEHOLDER_BOT)
            owner = user.get('bot', {}).get('owner', {})
            workspace_id = user.get('bot', {}).get('workspace_id') or owner.get('workspace_id')
            if isinstance(workspace_id, str) and workspace_id not in PLACEHOLDER_IDS:
                self._add(workspace_id, PLACEHOLDER_WORKSPACE)
        elif user.get('type') == 'person' and user['id'] not in self._placeholders:
            if self._persons_seen < len(PLACEHOLDER_PERSONS):
                self._add(user['id'], PLACEHOLDER_PERSONS[self._persons_seen])
                self._persons_seen += 1

    def scrub(self, text: str) -> str:
        """Replace every registered shared id (dashed and dash-less) with its placeholder."""
        for real_id, placeholder in self._placeholders.items():
            text = text.replace(real_id, placeholder).replace(_undash(real_id), _undash(placeholder))
        return text


# One registry for the whole session. During offline replay it only ever sees already-placeholder ids,
# which it refuses to learn, so it stays empty and the scrubbing is a no-op.
_shared_ids = _SharedIdRegistry()


def _scrub_request_body(body: Any) -> Any:
    """Return a request body with shared ids normalised, preserving its `str`/`bytes`/`None` type."""
    if isinstance(body, bytes):
        try:
            return _shared_ids.scrub(body.decode('utf-8')).encode('utf-8')
        except UnicodeDecodeError:
            return body
    if isinstance(body, str):
        return _shared_ids.scrub(body)
    return body


def normalize_shared_ids_request(request: Any) -> Any:
    """`before_record_request` hook: normalise shared ids in the request URI and body.

    Applied both when recording and (by VCR) over the outgoing request before matching, so cassettes
    recorded against different workspaces match each other.
    """
    request.uri = _shared_ids.scrub(request.uri)
    request.body = _scrub_request_body(request.body)
    return request


def pytest_addoption(parser: Parser) -> None:
    """Add flag to the pytest command line so that we can overwrite fixtures but not always!"""
    parser.addoption(
        '--debug-uno',
        action='store_true',
        default=False,
        help='Enable DEBUG logging for Ultimate Notion.',
    )
    for marker in PYTEST_MARKERS:
        flag = f'--{marker.replace("_", "-")}'
        parser.addoption(
            flag,
            action='store_true',
            default=False,
            help=f'Use flag `{flag}` to run tests marked with `{marker}`.',
        )


def pytest_exception_interact(node: pytest.Item, call: pytest.CallInfo[Any], report: pytest.TestReport) -> None:
    """Handle exceptions raised in the tests and provide a bit more output for some exceptions."""
    if call.excinfo is None:
        return
    exc_value = call.excinfo.value

    if isinstance(exc_value, pydantic.ValidationError):
        input_errors = '\n'.join(str(e['input']) for e in exc_value.errors())
        msg = f'Following erroneous inputs to the pydantic model {exc_value.title}:\n{input_errors}'
        logging.error(msg)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Define test selection based on command line flags."""

    def get_marker_option() -> str | None:
        markers = set()
        for marker in PYTEST_MARKERS:
            flag = f'--{marker.replace("_", "-")}'
            if config.getoption(flag):
                markers.add(marker)
        if len(markers) == 1:
            return markers.pop()
        elif len(markers) > 1:
            msg = f'Use only one of the mutually exclusive markers {PYTEST_MARKERS} at a time!'
            raise ValueError(msg)
        else:
            return None

    # Replay-only tests assert against a hand-crafted cassette that a live workspace cannot
    # reproduce (e.g. the fixed `search_page()` result set in issue #273). A live re-record
    # (`hatch run vcr-rewrite`, `--record-mode=rewrite`) would overwrite the crafted cassette
    # with real workspace data and break the test, so skip them in that mode. Every other mode
    # (`none`, `once`, `new_episodes`) replays the committed cassette and is safe.
    if config.getoption('--record-mode') == 'rewrite':
        skip_replay_only = pytest.mark.skip(
            reason='replay-only: crafted cassette must not be overwritten by a live re-record'
        )
        for item in items:
            if 'replay_only' in item.keywords:
                item.add_marker(skip_replay_only)

    marker = get_marker_option()
    if marker is None:
        for item in items:
            markers = set(item.keywords) & set(PYTEST_MARKERS)
            if markers:
                marker = markers.pop()
                flag = f'--{marker.replace("_", "-")}'
                skip_reason = pytest.mark.skip(reason=f'use flag `{flag}` to run {marker}')
                item.add_marker(skip_reason)
    else:
        selected_tests = [item for item in items if marker in item.keywords]
        if not selected_tests:
            pytest.skip(f'No tests with marker `{marker}` found!')
        items[:] = selected_tests


def exec_pyfile(file_path: str) -> None:
    """Executes a Python module as a script, as if it was called from the command line."""
    code = compile(Path(file_path).read_text(encoding='utf-8'), file_path, 'exec')
    exec(code, {'__MODULE__': '__main__'})  # noqa: S102


@pytest.fixture(scope='session', autouse=True)
def offline_replay_token(request: SubRequest) -> None:
    """Provide a dummy Notion token for pure offline replay (`hatch run vcr-only`).

    With `--record-mode=none` the network is blocked and every interaction is
    replayed from a cassette, so the token is never actually sent. Supplying a
    placeholder lets contributors run the offline suite with no credentials, as
    promised in `CONTRIBUTING.md`. Live and (re-)recording runs are untouched: a
    real token must be provided via `NOTION_TOKEN` for those.
    """
    replay_only = request.config.getoption('--record-mode') == 'none'
    if replay_only and not os.environ.get(ENV_NOTION_TOKEN):
        os.environ[ENV_NOTION_TOKEN] = 'secret...'  # never sent; the network is blocked during replay


@pytest.fixture(scope='session', autouse=True)
def activate_debug_mode(request: SubRequest) -> None:
    """Activates debug mode if set accordingly in the config file"""
    if request.config.getoption('--debug-uno'):
        os.environ[ENV_ULTIMATE_NOTION_DEBUG] = '1'


# Header/body fields that must never be committed to a cassette.
SECRET_PARAMS = [
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


def _redact_google_oauth_body(body: Any) -> Any:
    """Redact OAuth secrets carried in a Google API response body (the `body.string` back end)."""
    if not isinstance(body, str):
        return body
    try:
        dct = json.loads(body)
        for secret in SECRET_PARAMS:
            if secret in dct:
                dct[secret] = 'secret...'
        return json.dumps(dct)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body


def _normalize_ids_in_body(body: Any) -> Any:
    """Learn and normalise shared-object ids in a Notion response body (the `content` back end).

    VCR applies `before_record_response` on playback as well as on recording, so this must be
    *byte-preserving* for an already-normalised body: it only parses to learn ids and rewrites
    ids/titles by plain string replacement (a no-op once they are placeholders). It deliberately does
    NOT redact OAuth secrets or re-serialise -- Notion bodies carry no OAuth secrets, and `code` is a
    Notion *error code* (e.g. `object_not_found`), not a secret. Re-serialising would reflow the JSON,
    desync `Content-Length`, and corrupt the replay.
    """
    if not isinstance(body, str):
        return body
    with contextlib.suppress(json.JSONDecodeError, UnicodeDecodeError):
        _shared_ids.learn_from_response(json.loads(body))
    # Normalise a non-default root page title back to the canonical `Tests` so a recording made
    # against a differently named root (via `UNO_TEST_ROOT_PAGE`) replays against the committed
    # cassettes. A no-op for the default `Tests`, so existing cassettes are untouched.
    if TESTS_PAGE != 'Tests':
        body = body.replace(TESTS_PAGE, 'Tests')
    # Notion returns object URLs under either `www.notion.so/<id>` or `app.notion.com/p/<id>` depending
    # on the workspace/account. Canonicalise to `www.notion.so/` so a cassette recorded against an
    # app.notion.com workspace replays against the placeholder-based, notion.so expectations. The two
    # forms differ in length, but `Content-Length` is not stored in the cassettes, and on replay the body
    # already carries `www.notion.so`, so the replacement is then a no-op.
    body = body.replace('app.notion.com/p/', 'www.notion.so/')
    return _shared_ids.scrub(body)


def normalize_response(response: dict[str, Any]) -> dict[str, Any]:
    """`before_record_response` hook: drop secret headers and normalise the response body.

    Google (urllib) responses keep the body at `body.string`; Notion (httpx) responses keep it at
    `content`. Both back ends are handled so shared ids are normalised whichever one a cassette uses.
    """
    for secret in SECRET_PARAMS:
        response['headers'].pop(secret, None)
    if isinstance(response.get('body'), dict) and 'string' in response['body']:
        response['body']['string'] = _normalize_ids_in_body(_redact_google_oauth_body(response['body']['string']))
    elif 'content' in response:
        response['content'] = _normalize_ids_in_body(response['content'])
    return response


def build_vcr_config() -> dict[str, Any]:
    """Build the pytest-recording config (also reused when recording from module-level fixtures)."""
    return {
        'match_on': [*VCR_DEFAULT_MATCHERS, VCR_SEARCH_MATCHER, VCR_QUERY_MATCHER],
        'filter_headers': [(param, 'secret...') for param in SECRET_PARAMS],
        'filter_query_parameters': SECRET_PARAMS,
        'filter_post_data_parameters': SECRET_PARAMS,
        'before_record_request': normalize_shared_ids_request,
        'before_record_response': normalize_response,
    }


@pytest.fixture(scope='session')
def vcr_config() -> dict[str, Any]:
    """Configure pytest-recording."""
    return build_vcr_config()


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


class _NamedFunc(Protocol):
    """A callable with a `__name__`, i.e. a plain function (which `Callable` does not model)."""

    __name__: str

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


def vcr_fixture(
    scope: Literal['module', 'session'], *, autouse: bool = False, shared: bool = False
) -> Callable[..., Any]:
    """Return a VCR fixture for module/session-level fixtures"""
    if scope not in {'module', 'session'}:
        msg = f'Use this only for module or session scope, not {scope}!'
        raise ValueError(msg)

    def decorator(func: _NamedFunc) -> Callable[..., Any]:
        args = inspect.signature(func).parameters  # to inject the fixtures into the wrapper
        is_generator = inspect.isgeneratorfunction(func)

        def setup_vcr(request: SubRequest, vcr_config: dict[str, str]) -> tuple[VCR | MagicMock, str]:
            if scope == 'module' and not shared:
                cassette_dir = str(Path(request.module.__file__).parent / 'cassettes' / 'fixtures')
                cassette_name = f'mod_{func.__name__}.yaml'  # same cassette for all modules!
            else:
                cassette_dir = str(request.config.rootpath / 'tests' / 'cassettes' / 'fixtures')
                prefix = 'mod' if scope == 'module' else 'sess'
                cassette_name = f'{prefix}_{func.__name__}.yaml'

            vcr_config = vcr_config.copy()  # to avoid changing the original config
            vcr_config |= {'cassette_library_dir': cassette_dir}
            disable_recording = request.config.getoption('--disable-recording')
            if disable_recording:
                vcr: MagicMock = MagicMock()
                vcr.use_cassette.return_value.__enter__.return_value = None
            else:
                mode = request.config.getoption('--record-mode')
                if mode == 'rewrite':
                    # Re-record the shared fixture cassettes live (with real ids) on every rewrite.
                    # Replaying them (e.g. via `new_episodes`) would feed back the workspace-portable
                    # placeholder ids written by the normalisation, 404ing later modules in a full-suite
                    # re-record. Deterministic fixtures (e.g. `search('Tests')`) re-record identically.
                    mode = 'all'
                elif mode is None:
                    mode = 'none'
                vcr = VCR(record_mode=vcr_mode(mode), **vcr_config)
                register_notion_matchers(vcr)

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


def require_page(notion: Session, title: str) -> Page:
    """Return the named page, or skip the test if the workspace does not contain it.

    A fresh workspace will not have the manually created test objects, so depending
    tests skip with a helpful message instead of erroring. See the "Set up a Notion
    test workspace" section in `CONTRIBUTING.md`.
    """
    pages = notion.search_page(title)
    if not pages:
        pytest.skip(f'Test workspace has no page titled {title!r}; see CONTRIBUTING.md.')
    return pages.item()


def require_db(notion: Session, title: str) -> Database:
    """Return the named database, or skip the test if the workspace does not contain it."""
    dbs = notion.search_db(title)
    if not dbs:
        pytest.skip(f'Test workspace has no database titled {title!r}; see CONTRIBUTING.md.')
    return dbs.item()


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


@vcr_fixture(scope='module', shared=True)
def person(notion_cached: Session) -> User:
    """Return a user object for testing.

    Use the first user visible to the integration so the suite is not tied to a
    specific workspace member.
    """
    return notion_cached.all_users()[0]


@vcr_fixture(scope='module')
def contacts_db(notion_cached: Session) -> Database:
    """Return a test database."""
    return require_db(notion_cached, CONTACTS_DB)


@vcr_fixture(scope='module')
def root_page(notion_cached: Session) -> Page:
    """Return the page reference used as parent page for live testing."""
    return require_page(notion_cached, TESTS_PAGE)


@pytest.fixture(scope='function')
def article_db(notion_cached: Session, root_page: Page) -> Iterator[Database]:
    """Simple database of articles."""

    class Article(schema.Schema, db_title='Articles'):
        name = schema.Title('Name')
        cost = schema.Number('Cost', format=NumberFormat.DOLLAR)
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
    return require_page(notion_cached, GETTING_STARTED_PAGE)


@vcr_fixture(scope='module')
def all_props_db(notion_cached: Session) -> Database:
    """Return manually created database with all properties, also AI properties."""
    return require_db(notion_cached, ALL_PROPS_DB)


@vcr_fixture(scope='module')
def wiki_db(notion_cached: Session) -> Database:
    """Return manually created wiki db."""
    return require_db(notion_cached, WIKI_DB)


@vcr_fixture(scope='module')
def formula_db(notion_cached: Session) -> Database:
    """Return manually created formula db.

    Notion's eventually-consistent `/search` index intermittently reports the formula
    columns by their underlying storage type (e.g. `String` as `rich_text`), so reload
    from the authoritative database-retrieve endpoint to bind the true formula schema
    regardless of `/search` lag. `reload()`'s default `rebind_schema=True` would raise a
    `SchemaError` here, so `rebind_schema=False` is required.
    """
    db = require_db(notion_cached, FORMULA_DB)
    db.reload(rebind_schema=False)
    return db


@vcr_fixture(scope='module')
def md_text_page(notion_cached: Session) -> Page:
    """Return a page with markdown text content."""
    return require_page(notion_cached, MD_TEXT_TEST_PAGE)


@vcr_fixture(scope='module')
def md_page(notion_cached: Session) -> Page:
    """Return a page with markdown content."""
    return require_page(notion_cached, MD_PAGE_TEST_PAGE)


@vcr_fixture(scope='module')
def md_subpage(notion_cached: Session) -> Page:
    """Return a page with markdown content."""
    return require_page(notion_cached, MD_SUBPAGE_TEST_PAGE)


@vcr_fixture(scope='module')
def embed_page(notion_cached: Session) -> Page:
    """Return a page with embed/inline/linked & unfurl content."""
    return require_page(notion_cached, EMBED_TEST_PAGE)


@vcr_fixture(scope='module')
def comment_page(notion_cached: Session) -> Page:
    """Return a page with comments."""
    return require_page(notion_cached, COMMENT_PAGE)


@vcr_fixture(scope='module')
def custom_emoji_page(notion_cached: Session) -> Page:
    """Return a page with a custom emoji."""
    return require_page(notion_cached, CUSTOM_EMOJI_PAGE)


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
    return require_db(notion_cached, TASK_DB)


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
            'to perform the authentication flow before rewriting the VCR cassettes.\n'
            'Note that the missing authentication might have been recorded in the VCR cassettes!\n'
            'So running `hatch run vcr-drop-cassettes` might be necessary as well.'
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
        uno_blocks.Callout('Callout without icon'),
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
def dummy_urls() -> URL:
    """Return a set of URLs for testing."""
    return URL(
        img='https://cdn.pixabay.com/photo/2019/08/06/09/16/flowers-4387827_1280.jpg',
        file='https://www.google.de/robots.txt',
        video='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        pdf='https://www.rd.usda.gov/sites/default/files/pdf-sample_0.pdf',
        audio='https://samplelib.com/lib/preview/mp3/sample-3s.mp3',
    )


@pytest.fixture(scope='function')
def get_id_prefix(notion: uno.Session, root_page: uno.Page) -> Callable[[str], str]:
    """Return a unique id prefix for the test module.

    This is necessary as prefixes must be unique within the workspace. For VCR.py
    we need to have a stable prefix per module. Note that even the prefix of a deleted
    database is still reserved in Notion!
    """

    def make_prefix(suffix: str) -> str:
        state_page = notion.get_or_create_page(parent=root_page, title=f'State Page for ID Prefix {suffix}')
        if not state_page.children:
            upper_bound = int('9' * (10 - len(suffix)))  # Notion restriction to prefix length of 1
            state_block = uno.Paragraph(f'{suffix}{randint(0, upper_bound)}')  # noqa: S311
            state_page.append(state_block)

        state_page.reload()  # this saves actually the state in VCR.py
        first_child = state_page.children[0]
        assert isinstance(first_child, uno.Paragraph)
        id_prefix = first_child.rich_text
        if id_prefix is None:
            msg = 'Could not retrieve ID prefix from state page!'
            raise ValueError(msg)
        return id_prefix

    return make_prefix

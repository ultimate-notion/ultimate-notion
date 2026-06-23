"""Unit tests for the workspace-portable cassette helpers in `conftest` (issue #296).

These cover the pure shared-id normalisation logic (detection, scrubbing, the request hook). The
live *recording* path -- where the normalisation runs against real Notion responses -- can only be
exercised with a live workspace and is therefore validated by re-recording, not here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from tests import conftest
from tests.conftest import (
    PLACEHOLDER_BOT,
    PLACEHOLDER_PERSONS,
    PLACEHOLDER_WORKSPACE,
    SHARED_OBJECT_PLACEHOLDERS,
    TESTS_PAGE,
    _SharedIdRegistry,
    _undash,
    match_search_body,
    normalize_response,
    normalize_shared_ids_request,
)

ROOT_ID = '5f505199-b292-4713-920b-61d813bf72a3'
ROOT_PLACEHOLDER = SHARED_OBJECT_PLACEHOLDERS[TESTS_PAGE]
WORKSPACE_ID = '5a65efbd-bfb2-4ebe-bb5d-ac95c98fb252'
BOT_ID = '645e79dd-3e43-40de-9d51-39357c1c427f'


def _page(obj_id: str, title: str) -> dict[str, Any]:
    return {
        'object': 'page',
        'id': obj_id,
        'properties': {'title': {'type': 'title', 'title': [{'plain_text': title}]}},
    }


def _database(obj_id: str, title: str) -> dict[str, Any]:
    return {'object': 'database', 'id': obj_id, 'title': [{'plain_text': title}]}


def _bot_user(bot_id: str, workspace_id: str) -> dict[str, Any]:
    return {
        'object': 'user',
        'id': bot_id,
        'type': 'bot',
        'bot': {'owner': {'type': 'workspace', 'workspace': True}, 'workspace_id': workspace_id},
    }


def _person_user(person_id: str, name: str) -> dict[str, Any]:
    return {'object': 'user', 'id': person_id, 'type': 'person', 'person': {'email': f'{name}@example.com'}}


@dataclass
class _FakeRequest:
    """Minimal stand-in for a `vcr` request, exposing the `uri`/`body`/`path` the helpers read."""

    uri: str
    body: Any
    path: str = ''


def test_registry_learns_page_by_title() -> None:
    reg = _SharedIdRegistry()
    reg.learn_from_response(_page(ROOT_ID, TESTS_PAGE))
    assert reg.scrub(ROOT_ID) == ROOT_PLACEHOLDER


def test_registry_learns_database_by_title() -> None:
    reg = _SharedIdRegistry()
    db_id = 'b0cb6b70-e740-496d-9c81-8a298fa2d5e1'
    reg.learn_from_response(_database(db_id, 'Task DB'))
    assert reg.scrub(db_id) == SHARED_OBJECT_PLACEHOLDERS['Task DB']


def test_registry_ignores_unknown_title() -> None:
    reg = _SharedIdRegistry()
    ephemeral = 'deadbeef-0000-0000-0000-000000000000'
    reg.learn_from_response(_page(ephemeral, 'Some Created Page'))
    assert reg.scrub(ephemeral) == ephemeral  # unchanged


def test_registry_scrubs_dashed_and_dashless() -> None:
    reg = _SharedIdRegistry()
    reg.learn_from_response(_page(ROOT_ID, TESTS_PAGE))
    text = f'path /{ROOT_ID}/children and url notion.so/Tests-{_undash(ROOT_ID)}'
    scrubbed = reg.scrub(text)
    assert ROOT_ID not in scrubbed and _undash(ROOT_ID) not in scrubbed
    assert ROOT_PLACEHOLDER in scrubbed and _undash(ROOT_PLACEHOLDER) in scrubbed


def test_registry_learns_bot_and_workspace() -> None:
    reg = _SharedIdRegistry()
    reg.learn_from_response(_bot_user(BOT_ID, WORKSPACE_ID))
    assert reg.scrub(BOT_ID) == PLACEHOLDER_BOT
    assert reg.scrub(WORKSPACE_ID) == PLACEHOLDER_WORKSPACE


def test_registry_learns_persons_in_first_seen_order() -> None:
    reg = _SharedIdRegistry()
    first, second = 'aaaaaaaa-0000-0000-0000-000000000000', 'bbbbbbbb-0000-0000-0000-000000000000'
    reg.learn_from_response({'results': [_person_user(first, 'first'), _person_user(second, 'second')]})
    assert reg.scrub(first) == PLACEHOLDER_PERSONS[0]
    assert reg.scrub(second) == PLACEHOLDER_PERSONS[1]


def test_registry_person_id_is_stable_once_registered() -> None:
    reg = _SharedIdRegistry()
    pid = 'aaaaaaaa-0000-0000-0000-000000000000'
    reg.learn_from_response(_person_user(pid, 'p'))
    reg.learn_from_response(_person_user(pid, 'p'))  # seen again
    assert reg.scrub(pid) == PLACEHOLDER_PERSONS[0]


def test_empty_registry_is_a_noop() -> None:
    # Mirrors offline replay: nothing recorded, so scrubbing must not touch the text.
    text = f'/{ROOT_ID}/children'
    assert _SharedIdRegistry().scrub(text) == text


@pytest.fixture
def _registered_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the module-global registry used by the request hook at one that knows the root page."""
    reg = _SharedIdRegistry()
    reg.learn_from_response(_page(ROOT_ID, TESTS_PAGE))
    monkeypatch.setattr(conftest, '_shared_ids', reg)


@pytest.mark.usefixtures('_registered_root')
def test_request_hook_scrubs_uri() -> None:
    req = normalize_shared_ids_request(_FakeRequest(f'https://api.notion.com/v1/blocks/{ROOT_ID}/children', None))
    assert ROOT_ID not in req.uri and ROOT_PLACEHOLDER in req.uri


@pytest.mark.usefixtures('_registered_root')
def test_request_hook_scrubs_str_body() -> None:
    req = normalize_shared_ids_request(_FakeRequest('https://api.notion.com/v1/search', json.dumps({'p': ROOT_ID})))
    assert json.loads(req.body)['p'] == ROOT_PLACEHOLDER


@pytest.mark.usefixtures('_registered_root')
def test_request_hook_scrubs_bytes_body_preserving_type() -> None:
    req = normalize_shared_ids_request(_FakeRequest('https://x', json.dumps({'p': ROOT_ID}).encode()))
    assert isinstance(req.body, bytes)
    assert json.loads(req.body)['p'] == ROOT_PLACEHOLDER


@pytest.mark.usefixtures('_registered_root')
def test_request_hook_leaves_none_body() -> None:
    req = normalize_shared_ids_request(_FakeRequest('https://x', None))
    assert req.body is None


def test_matcher_compares_search_requests_by_body() -> None:
    path = conftest.NOTION_SEARCH_PATH
    a = _FakeRequest('https://api.notion.com/v1/search', json.dumps({'query': 'A'}), path=path)
    b = _FakeRequest('https://api.notion.com/v1/search', json.dumps({'query': 'B'}), path=path)
    assert match_search_body(a, a)
    assert not match_search_body(a, b)


def test_matcher_passes_non_search_requests() -> None:
    a = _FakeRequest('https://api.notion.com/v1/pages', json.dumps({'query': 'A'}), path='/v1/pages')
    b = _FakeRequest('https://api.notion.com/v1/pages', json.dumps({'query': 'B'}), path='/v1/pages')
    assert match_search_body(a, b)


@pytest.fixture
def _fresh_registry(monkeypatch: pytest.MonkeyPatch) -> _SharedIdRegistry:
    """Swap in an empty module-global registry so `normalize_response` starts from a clean slate."""
    reg = _SharedIdRegistry()
    monkeypatch.setattr(conftest, '_shared_ids', reg)
    return reg


def test_normalize_response_handles_notion_content_shape(_fresh_registry: _SharedIdRegistry) -> None:
    # Notion (httpx) responses keep the body under `content`; this is the shape that originally slipped
    # through unnormalised. Learning + scrubbing must apply to it.
    response = {'headers': {'authorization': 'secret'}, 'content': json.dumps(_page(ROOT_ID, TESTS_PAGE))}
    out = normalize_response(response)
    assert ROOT_ID not in out['content'] and ROOT_PLACEHOLDER in out['content']
    assert 'authorization' not in out['headers']


def test_normalize_response_handles_google_body_string_shape(_fresh_registry: _SharedIdRegistry) -> None:
    # Google (urllib) responses keep the body under `body.string`.
    response = {'headers': {}, 'body': {'string': json.dumps(_page(ROOT_ID, TESTS_PAGE))}}
    out = normalize_response(response)
    assert ROOT_ID not in out['body']['string'] and ROOT_PLACEHOLDER in out['body']['string']


def test_notion_error_response_is_byte_preserved(_fresh_registry: _SharedIdRegistry) -> None:
    # `code` is in SECRET_PARAMS (the Google OAuth code) but is also a Notion *error code*. The Notion
    # `content` branch must NOT redact/re-serialise it: a reflowed 404 body desyncs Content-Length and
    # corrupts replay. The body must come back byte-for-byte identical.
    content = '{"object":"error","status":404,"code":"object_not_found","message":"Not found"}'
    out = normalize_response({'headers': {}, 'content': content})
    assert out['content'] == content


def test_relearning_placeholders_keeps_registry_empty(_fresh_registry: _SharedIdRegistry) -> None:
    # On playback the hooks re-see already-placeholder responses; learning must be idempotent so the
    # registry stays empty and persons (assigned by first-seen order) are not remapped.
    reg = _fresh_registry
    reg.learn_from_response(_page(ROOT_PLACEHOLDER, TESTS_PAGE))
    reg.learn_from_response(_person_user(PLACEHOLDER_PERSONS[1], 'p'))  # a placeholder person seen "first"
    text = f'/{ROOT_PLACEHOLDER}/x {PLACEHOLDER_PERSONS[1]}'
    assert reg.scrub(text) == text

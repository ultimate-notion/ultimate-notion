"""Verify that workspace bootstrap creates and reuses a linked view."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest

from scripts.bootstrap_test_workspace import Bootstrap, RetryingClient
from tests._views_vcr import normalize_test_root_response
from tests.conftest import TESTS_PAGE
from ultimate_notion import DataSource, Page, Session
from ultimate_notion.obj_api import NOTION_API_VERSION
from ultimate_notion.obj_api import blocks as obj_blocks

PAGE_ID = '701e9132-4fb6-4d6b-8cdb-e556333affd8'
SOURCE_ID = '991b892a-dd14-48a6-b93e-722bc5659a22'
LINKED_DB_ID = 'df2dfbb0-f527-4136-b31a-c0d50bef1179'
VIEW_ID = 'bbfd6492-70e7-4e58-8982-e5d8ff8d1ffa'


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Skip live workspace cleanup for the mock transport."""


@pytest.mark.parametrize('already_linked', [False, True])
def test_bootstrap_embed_page_reuses_linked_view(*, already_linked: bool) -> None:
    link = {
        'object': 'block',
        'type': 'child_database',
        'id': LINKED_DB_ID,
        'child_database': {'title': 'Task DB'},
    }
    blocks = [link] if already_linked else []
    create_requests: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        match request.method, request.url.path:
            case 'GET', path if path == f'/v1/blocks/{PAGE_ID}/children':
                return httpx.Response(200, json={'object': 'list', 'type': 'block', 'block': {}, 'results': blocks})
            case 'GET', path if path == f'/v1/databases/{LINKED_DB_ID}':
                return httpx.Response(
                    404, json={'object': 'error', 'code': 'object_not_found', 'message': 'Linked database'}
                )
            case 'POST', '/v1/views':
                assert request.headers['Notion-Version'] == NOTION_API_VERSION
                create_requests.append(json.loads(request.content))
                blocks.append(link)
                return httpx.Response(
                    200,
                    json={
                        'object': 'view',
                        'type': 'table',
                        'id': VIEW_ID,
                        'parent': {'type': 'database_id', 'database_id': LINKED_DB_ID},
                    },
                )
            case _:
                pytest.fail(f'Unexpected request {request.method} {request.url.path}')

    client = RetryingClient(
        auth='test', notion_version=NOTION_API_VERSION, client=httpx.Client(transport=httpx.MockTransport(handle))
    )
    with Session(client=client) as notion:
        bootstrap = Bootstrap.for_audit(notion)
        page = Page.wrap_obj_ref(
            obj_blocks.Page.model_validate({'id': PAGE_ID, 'parent': {'type': 'workspace', 'workspace': True}})
        )
        task_ds = DataSource.wrap_obj_ref(obj_blocks.DataSource.model_validate({'id': SOURCE_ID}))
        with patch.object(bootstrap, 'create_page', return_value=page):
            bootstrap.ensure_embed_page(task_ds)
            bootstrap.ensure_embed_page(task_ds)
        assert page.children[-1].id == UUID(LINKED_DB_ID)

    assert create_requests == (
        []
        if already_linked
        else [
            {
                'name': 'Tasks',
                'type': 'table',
                'data_source_id': SOURCE_ID,
                'create_database': {'parent': {'type': 'page_id', 'page_id': PAGE_ID}},
            }
        ]
    )


@pytest.mark.vcr(before_record_response=normalize_test_root_response, decode_compressed_response=True)
def test_bootstrap_linked_view_round_trip() -> None:
    with Session() as notion:
        bootstrap = Bootstrap(notion, TESTS_PAGE)
        workspace = notion.create_page(bootstrap.root, title='Linked view bootstrap test')
        bootstrap.root = workspace
        try:
            task_ds = notion.create_ds(workspace, title='Bootstrap test tasks')
            # Restrict the fixture lookup to this run's page. The normal bootstrap
            # searches by title across the workspace, where the shared fixture may exist.
            with patch.object(bootstrap, 'find_page', return_value=None) as find_page:
                page = bootstrap.ensure_embed_page(task_ds)
                assert len(page.children) == 4
                assert page.to_markdown().rstrip().endswith('<kbd>↗️ Linked database (unsupported)</kbd>')
                linked_db_id = page.children[-1].id

                page.reload()
                find_page.return_value = page
                repeated = bootstrap.ensure_embed_page(task_ds)
                assert len(repeated.children) == 4
                assert repeated.children[-1].id == linked_db_id
        finally:
            workspace.delete()

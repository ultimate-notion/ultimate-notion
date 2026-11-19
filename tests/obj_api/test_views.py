"""HTTP contract tests for saved database views."""

from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest
from notion_client import Client

from ultimate_notion import Session, ViewType
from ultimate_notion.obj_api import NOTION_API_VERSION

PAGE_ID = '21e91325-4fb6-4d6b-8cdb-e556333affd8'
DATABASE_ID = 'df2dfbb0-f527-4136-b31a-c0d50bef1179'
SOURCE_ID = '991b892a-dd14-48a6-b93e-722bc5659a22'
VIEW_ID = 'bbfd6492-70e7-4e58-8982-e5d8ff8d1ffa'


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Skip live workspace cleanup for mock transport tests."""


def test_saved_view_lifecycle() -> None:
    view = {
        'object': 'view',
        'id': VIEW_ID,
        'parent': {'type': 'database_id', 'database_id': DATABASE_ID},
        'data_source_id': SOURCE_ID,
        'type': 'table',
        'name': 'Tasks',
    }
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == 'PATCH':
            view.update(json.loads(request.content))
        return httpx.Response(200, json=view)

    transport = httpx.MockTransport(handle)
    client = Client(auth='test', notion_version=NOTION_API_VERSION, client=httpx.Client(transport=transport))
    with Session(client=client) as notion:
        created = notion.api.views.create(name='Tasks', view_type=ViewType.TABLE, data_source=SOURCE_ID, page=PAGE_ID)
        assert created.parent.database_id == UUID(DATABASE_ID)
        saved = notion.get_view(created.id)
        assert saved.type is ViewType.TABLE
        assert saved.data_source_id == UUID(SOURCE_ID)
        assert saved.update(name='Open tasks', filter=None).name == 'Open tasks'
        saved.delete()

    assert [(req.method, req.url.path) for req in requests] == [
        ('POST', '/v1/views'),
        ('GET', f'/v1/views/{VIEW_ID}'),
        ('PATCH', f'/v1/views/{VIEW_ID}'),
        ('DELETE', f'/v1/views/{VIEW_ID}'),
    ]
    assert json.loads(requests[0].content) == {
        'name': 'Tasks',
        'type': 'table',
        'data_source_id': SOURCE_ID,
        'create_database': {'parent': {'type': 'page_id', 'page_id': PAGE_ID}},
    }
    assert json.loads(requests[2].content) == {'name': 'Open tasks', 'filter': None}


def test_list_saved_views_follows_cursor() -> None:
    cursor = 'opaque:cursor+next/='
    queries: list[dict[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == 'GET'
        assert request.url.path == '/v1/views'
        queries.append(dict(request.url.params))
        first_page = len(queries) == 1
        return httpx.Response(
            200,
            json={
                'object': 'list',
                'type': 'view',
                'view': {},
                'results': [] if first_page else [{'object': 'view', 'id': VIEW_ID}],
                'has_more': first_page,
                'next_cursor': cursor if first_page else None,
            },
        )

    client = Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(handle)))
    with Session(client=client) as notion:
        assert [view.id for view in notion.api.views.list(database=DATABASE_ID)] == [UUID(VIEW_ID)]
    assert queries == [
        {'database_id': DATABASE_ID, 'page_size': '100'},
        {'database_id': DATABASE_ID, 'page_size': '100', 'start_cursor': cursor},
    ]

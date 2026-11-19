from __future__ import annotations

import json

import httpx
import pytest
from notion_client import Client

from ultimate_notion.obj_api.endpoints import NotionAPI
from ultimate_notion.obj_api.query import DataSourceQuery, Query, SearchQuery


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for query-model tests."""


@pytest.mark.parametrize('query_type', [DataSourceQuery, SearchQuery])
@pytest.mark.parametrize('cursor', ['opaque-session-cursor:abc', '598337872cf94fdf8782e53db20768a5'])
def test_opaque_query_cursor(query_type: type[Query], cursor: str) -> None:
    assert query_type(start_cursor=cursor).serialize_for_api()['start_cursor'] == cursor


def test_resume_validated_query_with_opaque_cursors() -> None:
    data_source_id = '59833787-2cf9-4fdf-8782-e53db20768a5'
    next_cursors = iter(('session:next', None))
    sent_cursors: list[str] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        assert request.method == 'POST'
        assert request.url.path == f'/v1/data_sources/{data_source_id}/query'
        sent_cursors.append(json.loads(request.content)['start_cursor'])
        next_cursor = next(next_cursors)
        return httpx.Response(
            200,
            json={
                'object': 'list',
                'type': 'page_or_data_source',
                'page_or_data_source': {},
                'results': [],
                'has_more': next_cursor is not None,
                'next_cursor': next_cursor,
            },
        )

    transport = httpx.MockTransport(handle_request)
    with httpx.Client(transport=transport) as http_client:
        client = Client(auth='secret', client=http_client)
        builder = NotionAPI(client).data_sources.query(data_source_id)
        builder.query = DataSourceQuery(start_cursor='session:resume')
        assert list(builder.execute()) == []

    assert sent_cursors == ['session:resume', 'session:next']

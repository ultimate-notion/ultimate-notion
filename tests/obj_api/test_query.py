from __future__ import annotations

from unittest.mock import Mock

import pytest

from ultimate_notion.obj_api.query import DataSourceQuery, DataSourceQueryBuilder, Query, SearchQuery


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for query-model tests."""


@pytest.mark.parametrize('query_type', [DataSourceQuery, SearchQuery])
@pytest.mark.parametrize('cursor', ['opaque-session-cursor:abc', '598337872cf94fdf8782e53db20768a5'])
def test_opaque_query_cursor(query_type: type[Query], cursor: str) -> None:
    assert query_type(start_cursor=cursor).serialize_for_api()['start_cursor'] == cursor


def test_resume_validated_query_with_opaque_cursors() -> None:
    response = {'object': 'list', 'type': 'page_or_data_source', 'page_or_data_source': {}, 'results': []}
    endpoint = Mock(
        side_effect=[
            response | {'has_more': True, 'next_cursor': 'session:next'},
            response | {'has_more': False, 'next_cursor': None},
        ]
    )
    builder = DataSourceQueryBuilder(endpoint, data_source_id='59833787-2cf9-4fdf-8782-e53db20768a5')
    builder.query = DataSourceQuery(start_cursor='session:resume')

    assert list(builder.execute()) == []
    assert [call.kwargs['start_cursor'] for call in endpoint.call_args_list] == ['session:resume', 'session:next']

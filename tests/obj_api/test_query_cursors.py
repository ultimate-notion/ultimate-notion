from __future__ import annotations

from unittest.mock import Mock
from uuid import UUID

import pytest

from ultimate_notion.obj_api.query import DataSourceQuery, DataSourceQueryBuilder


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for isolated unit tests."""


def test_uuid_cursor_compatibility() -> None:
    cursor = UUID('59833787-2cf9-4fdf-8782-e53db20768a5')
    assert DataSourceQuery(start_cursor=cursor).serialize_for_api()['start_cursor'] == str(cursor)


def test_execute_cursor_override_and_pagination() -> None:
    response = {'object': 'list', 'type': 'page_or_data_source', 'page_or_data_source': {}, 'results': []}
    endpoint = Mock(
        side_effect=[
            response | {'has_more': True, 'next_cursor': 'session:next'},
            response | {'has_more': False, 'next_cursor': None},
        ]
    )
    builder = DataSourceQueryBuilder(endpoint, data_source_id='59833787-2cf9-4fdf-8782-e53db20768a5')

    assert list(builder.execute(start_cursor='session:resume')) == []
    assert [call.kwargs['start_cursor'] for call in endpoint.call_args_list] == ['session:resume', 'session:next']

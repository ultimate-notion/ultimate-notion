from __future__ import annotations

import pytest
from notion_client import Client
from vcr.cassette import Cassette  # type: ignore[import-untyped]

from ultimate_notion.obj_api.endpoints import NotionAPI
from ultimate_notion.obj_api.query import DataSourceQuery, Query, SearchQuery


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for query-model tests."""


@pytest.mark.parametrize('query_type', [DataSourceQuery, SearchQuery])
@pytest.mark.parametrize('cursor', ['opaque-session-cursor:abc', '598337872cf94fdf8782e53db20768a5'])
def test_opaque_query_cursor(query_type: type[Query], cursor: str) -> None:
    assert query_type(start_cursor=cursor).serialize_for_api()['start_cursor'] == cursor


@pytest.mark.vcr(record_mode='none')
def test_resume_validated_query_with_opaque_cursors(vcr: Cassette | None) -> None:
    if vcr is None:
        pytest.skip('This synthetic cassette is replay-only')

    with Client(auth='secret') as client:
        builder = NotionAPI(client).data_sources.query('59833787-2cf9-4fdf-8782-e53db20768a5')
        builder.query = DataSourceQuery(start_cursor='session:resume')
        assert list(builder.execute()) == []

    assert vcr.all_played

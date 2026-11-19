from __future__ import annotations

from contextlib import closing

import pytest
from notion_client import Client
from vcr.cassette import Cassette  # type: ignore[import-untyped]

from ultimate_notion.obj_api.endpoints import NotionAPI
from ultimate_notion.obj_api.iterator import MAX_PAGE_SIZE, PageOrDataSourceList
from ultimate_notion.obj_api.query import DataSourceQuery, Query, SearchQuery


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for query-model tests."""


@pytest.mark.parametrize('query_type', [DataSourceQuery, SearchQuery])
@pytest.mark.parametrize('cursor', ['opaque-session-cursor:abc', '598337872cf94fdf8782e53db20768a5'])
def test_opaque_query_cursor(query_type: type[Query], cursor: str) -> None:
    assert query_type(start_cursor=cursor).serialize_for_api()['start_cursor'] == cursor


@pytest.mark.vcr('../../../cassettes/test_database/test_more_than_max_page_size_pages.yaml', record_mode='none')
def test_resume_validated_query_with_opaque_cursors(vcr: Cassette | None) -> None:
    if vcr is None:
        pytest.skip('This test reuses the database pagination recording')

    # The pagination test creates a new data source each time the cassette is recorded.
    query_request = next(request for request in vcr.requests if request.path.endswith('/query'))
    data_source_id = query_request.path.split('/')[-2]
    with closing(Client(auth='secret')) as client:
        first_page = PageOrDataSourceList.model_validate(
            client.data_sources.query(data_source_id=data_source_id, page_size=MAX_PAGE_SIZE)
        )
        assert first_page.has_more
        assert first_page.next_cursor is not None

        builder = NotionAPI(client).data_sources.query(data_source_id)
        builder.query = DataSourceQuery(start_cursor=first_page.next_cursor)
        assert len(list(builder.execute())) + len(first_page.results) == 110

    assert vcr.play_count == 2

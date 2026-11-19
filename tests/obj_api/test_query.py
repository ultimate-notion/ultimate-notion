from __future__ import annotations

import pytest

import ultimate_notion as uno
from ultimate_notion.obj_api.blocks import Page
from ultimate_notion.obj_api.iterator import PageOrDataSourceList
from ultimate_notion.obj_api.query import DataSourceQuery, Query, SearchQuery


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """These tests do not modify workspace data."""


@pytest.mark.parametrize('query_type', [DataSourceQuery, SearchQuery])
@pytest.mark.parametrize('cursor', ['opaque-session-cursor:abc', '598337872cf94fdf8782e53db20768a5'])
def test_opaque_query_cursor(query_type: type[Query], cursor: str) -> None:
    assert query_type(start_cursor=cursor).serialize_for_api()['start_cursor'] == cursor


@pytest.mark.vcr()
def test_resume_validated_query_with_opaque_cursors(notion: uno.Session) -> None:
    title = 'Contacts DB'
    response = notion.api.client.search(query=title, filter={'property': 'object', 'value': 'data_source'})
    assert isinstance(response, dict)
    (contacts_db,) = (
        result for result in response['results'] if ''.join(text['plain_text'] for text in result['title']) == title
    )
    data_source_id = contacts_db['id']
    first_page = PageOrDataSourceList.model_validate(
        notion.api.data_sources.raw_api.query(data_source_id=data_source_id, page_size=1)
    )
    assert first_page.has_more
    assert first_page.next_cursor is not None
    (initial,) = first_page.results
    assert isinstance(initial, Page)

    builder = notion.api.data_sources.query(data_source_id)
    builder.query = DataSourceQuery(start_cursor=first_page.next_cursor, page_size=1)
    resumed = next(builder.execute())
    assert resumed.id != initial.id

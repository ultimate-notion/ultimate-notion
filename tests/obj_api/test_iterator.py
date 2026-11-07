from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from ultimate_notion.database import DataSource as DataSourceWrapper
from ultimate_notion.errors import IncompleteQueryError
from ultimate_notion.obj_api.blocks import DataSource, Page
from ultimate_notion.obj_api.iterator import EndpointIterator, ObjectList
from ultimate_notion.obj_api.query import DataSourceQueryBuilder
from ultimate_notion.query import Query


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for response-parsing tests."""


def test_object_list_tolerates_pages_without_properties() -> None:
    """A search result whose page objects omit `properties` must still validate.

    Notion's `search` endpoint returns stripped-down records (e.g. trashed or
    limited-access pages) that contain essentially only `{'object': 'page', 'id': ...}`.
    `Page.properties` must therefore default to an empty dict rather than being
    required, otherwise the whole `ObjectList` fails to validate. Regression test
    for https://github.com/ultimate-notion/ultimate-notion/issues/273.
    """
    obj_list = ObjectList.model_validate(
        {
            'object': 'list',
            'type': 'page_or_database',
            'page_or_database': {},
            'has_more': False,
            'next_cursor': None,
            'results': [{'object': 'page', 'id': f'00000000-0000-4713-920b-61d813bf72a{i}'} for i in range(3)],
        }
    )

    assert len(obj_list.results) == 3
    for result in obj_list.results:
        assert isinstance(result, Page)
        assert result.properties == {}


def test_object_list_tolerates_data_sources_without_properties() -> None:
    """A search result whose data-source objects omit `properties` must still validate.

    Companion to the page case above: `DataSource.properties` must also default to an
    empty dict so stripped-down data-source records do not break `ObjectList` validation.
    """
    obj_list = ObjectList.model_validate(
        {
            'object': 'list',
            'type': 'page_or_data_source',
            'page_or_data_source': {},
            'has_more': False,
            'next_cursor': None,
            'results': [{'object': 'data_source', 'id': f'00000000-0000-4713-920b-61d813bf72a{i}'} for i in range(3)],
        }
    )

    assert len(obj_list.results) == 3
    for result in obj_list.results:
        assert isinstance(result, DataSource)
        assert result.properties == {}


@pytest.mark.parametrize('status', [None, {'type': 'complete'}])
def test_complete_query_status(status: dict[str, str] | None) -> None:
    response: dict[str, Any] = {
        'object': 'list',
        'type': 'page_or_data_source',
        'page_or_data_source': {},
        'results': [],
        'has_more': False,
        'next_cursor': None,
    }
    if status is not None:
        response['request_status'] = status
    assert list(EndpointIterator(Mock(return_value=response))()) == []


@pytest.mark.parametrize('previous_page', [False, True])
def test_incomplete_query_raises(*, previous_page: bool) -> None:
    page_id = '59833787-2cf9-4fdf-8782-e53db20768a5'
    response = {
        'object': 'list',
        'type': 'page_or_data_source',
        'page_or_data_source': {},
        'results': [{'object': 'page', 'id': page_id}],
        'has_more': False,
        'next_cursor': None,
    }
    incomplete = response | {
        'request_status': {'type': 'incomplete', 'incomplete_reason': 'query_result_limit_reached'},
    }
    responses = (
        [response | {'has_more': True, 'next_cursor': 'opaque:next'}, incomplete] if previous_page else [incomplete]
    )
    endpoint = Mock(side_effect=responses)
    iterator = EndpointIterator[Page](endpoint)()
    if previous_page:
        assert str(next(iterator).id) == page_id
    with pytest.raises(IncompleteQueryError, match='query_result_limit_reached') as error:
        list(iterator)
    assert error.value.reason == 'query_result_limit_reached'
    assert endpoint.call_count == len(responses)


def test_high_level_query_does_not_return_partial_view(monkeypatch: pytest.MonkeyPatch) -> None:
    response = {
        'object': 'list',
        'type': 'page_or_data_source',
        'page_or_data_source': {},
        'results': [],
        'has_more': False,
        'next_cursor': None,
        'request_status': {'type': 'incomplete', 'incomplete_reason': 'query_result_limit_reached'},
    }
    ds_id = '59833787-2cf9-4fdf-8782-e53db20768a5'
    ds = DataSourceWrapper.wrap_obj_ref(DataSource.model_validate({'id': ds_id, 'title': []}))
    session = Mock()
    session.api.data_sources.query.return_value = DataSourceQueryBuilder(Mock(return_value=response), ds_id)
    monkeypatch.setattr('ultimate_notion.query.get_active_session', lambda: session)

    with pytest.raises(IncompleteQueryError):
        Query(ds).execute()

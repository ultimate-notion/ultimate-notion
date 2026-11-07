from __future__ import annotations

from unittest.mock import Mock

import pytest
from pydantic import ConfigDict

from ultimate_notion.database import DataSource as DataSourceWrapper
from ultimate_notion.errors import IncompleteQueryError
from ultimate_notion.obj_api.blocks import DataSource, Page
from ultimate_notion.obj_api.iterator import EndpointIterator, ObjectList, PageOrDataSourceList
from ultimate_notion.query import Query


class LenientPageList(PageOrDataSourceList):
    """Parse responses with release-style extra-field handling."""

    model_config = ConfigDict(extra='ignore')


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


def test_complete_query_status() -> None:
    response = {
        'object': 'list',
        'type': 'page_or_data_source',
        'page_or_data_source': {},
        'results': [],
        'has_more': False,
        'next_cursor': None,
        'request_status': {'type': 'complete'},
    }
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
    iterator = EndpointIterator[Page](endpoint, model_validate=LenientPageList.model_validate)()
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
    ds = DataSourceWrapper.wrap_obj_ref(
        DataSource.model_validate(
            {
                'id': ds_id,
                'title': [],
                'properties': {'Name': {'id': 'title', 'name': 'Name', 'type': 'title', 'title': {}}},
            }
        )
    )
    session = Mock()
    session.api.data_sources.query.return_value.execute.side_effect = EndpointIterator[Page](
        Mock(return_value=response), model_validate=LenientPageList.model_validate
    )
    monkeypatch.setattr('ultimate_notion.query.get_active_session', lambda: session)

    with pytest.raises(IncompleteQueryError):
        Query(ds).execute()

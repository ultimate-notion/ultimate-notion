from __future__ import annotations

from itertools import islice
from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import ConfigDict

import ultimate_notion as uno
from tests.conftest import require_ds
from ultimate_notion.errors import IncompleteQueryWarning
from ultimate_notion.obj_api.blocks import DataSource, Page
from ultimate_notion.obj_api.iterator import EndpointIterator, ObjectList, PageOrDataSourceList


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
    iterator = EndpointIterator[Page](Mock(return_value=response))
    assert list(iterator()) == []
    assert iterator.incomplete_status is None


@pytest.mark.parametrize('earlier_page_status', [None, 'complete', 'incomplete'])
def test_incomplete_query_preserves_results(earlier_page_status: str | None) -> None:
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
    responses = [incomplete]
    if earlier_page_status is not None:
        previous = (
            incomplete if earlier_page_status == 'incomplete' else response | {'request_status': {'type': 'complete'}}
        )
        responses.insert(0, previous | {'has_more': True, 'next_cursor': 'opaque:next'})
    endpoint = Mock(side_effect=responses)
    iterator = EndpointIterator[Page](endpoint, model_validate=LenientPageList.model_validate)
    with pytest.warns(IncompleteQueryWarning, match='query_result_limit_reached') as warnings:
        assert [str(page.id) for page in iterator()] == [page_id] * len(responses)

    assert len(warnings) == 1
    assert iterator.incomplete_status is not None
    assert iterator.incomplete_status.incomplete_reason == 'query_result_limit_reached'
    assert endpoint.call_count == len(responses)


@pytest.mark.vcr()
def test_capped_query_yields_first_page(notion: uno.Session) -> None:
    """Record against a dedicated data source with more than 10,000 rows."""
    ds = require_ds(notion, 'Ultimate Notion query cap test')

    results = notion.api.data_sources.query(ds.obj_ref).execute()
    with pytest.warns(IncompleteQueryWarning, match='query_result_limit_reached'):
        assert len(list(islice(results, 100))) == 100


def test_query_response_without_request_status() -> None:
    page_id = UUID('59833787-2cf9-4fdf-8782-e53db20768a5')
    response = {
        'object': 'list',
        'type': 'page_or_data_source',
        'page_or_data_source': {},
        'results': [{'object': 'page', 'id': str(page_id)}],
        'has_more': False,
        'next_cursor': None,
    }
    pages = list(EndpointIterator[Page](Mock(return_value=response))())
    assert [page.id for page in pages] == [page_id]

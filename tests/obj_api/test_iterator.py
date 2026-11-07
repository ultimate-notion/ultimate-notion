from __future__ import annotations

from unittest.mock import Mock
from uuid import UUID

import pytest

from ultimate_notion.obj_api.blocks import DataSource, Page
from ultimate_notion.obj_api.iterator import EndpointIterator, ObjectList


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


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for response-parsing tests."""


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

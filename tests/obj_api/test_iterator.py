from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import httpx
import notion_client
import pytest
from pydantic import ConfigDict

from ultimate_notion.config import Config, UNOCfg
from ultimate_notion.errors import IncompleteQueryError
from ultimate_notion.obj_api import NOTION_API_VERSION
from ultimate_notion.obj_api.blocks import DataSource, Page
from ultimate_notion.obj_api.iterator import EndpointIterator, ObjectList, PageOrDataSourceList
from ultimate_notion.session import Session


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


def test_high_level_query_does_not_return_partial_view(tmp_path: Path) -> None:
    ds_id = '59833787-2cf9-4fdf-8782-e53db20768a5'
    page_id = 'd1a617a5-b98b-4bd4-886f-c8582c8503e7'
    reason = 'query_result_limit_reached'
    ds_path = f'/v1/data_sources/{ds_id}'
    requests: list[tuple[str, str]] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        assert len(requests) < 2, 'A capped query should stop after the first query response'
        requests.append((request.method, request.url.path))
        if request.method == 'GET':
            return httpx.Response(
                200,
                json={
                    'object': 'data_source',
                    'id': ds_id,
                    'title': [],
                    'properties': {'Name': {'id': 'title', 'name': 'Name', 'type': 'title', 'title': {}}},
                },
            )
        return httpx.Response(
            200,
            json={
                'object': 'list',
                'type': 'page_or_data_source',
                'page_or_data_source': {},
                'results': [
                    {
                        'object': 'page',
                        'id': page_id,
                        'parent': {'type': 'data_source_id', 'data_source_id': ds_id},
                        'properties': {'Name': {'id': 'title', 'type': 'title', 'title': []}},
                    }
                ],
                'has_more': True,
                'next_cursor': 'opaque:next',
                'request_status': {'type': 'incomplete', 'incomplete_reason': reason},
            },
        )

    cfg = Config(ultimate_notion=UNOCfg(cfg_path=Path(__file__), sync_state_dir=tmp_path))
    http_client = httpx.Client(transport=httpx.MockTransport(handle_request))
    client = notion_client.Client(auth='test-token', client=http_client, notion_version=NOTION_API_VERSION)
    with Session(cfg, client=client) as session:
        ds = session.get_ds(ds_id)
        with pytest.raises(IncompleteQueryError, match=reason) as error:
            ds.query.execute()

    assert error.value.reason == reason
    assert requests == [('GET', ds_path), ('POST', f'{ds_path}/query')]


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

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, Mock
from uuid import UUID

import pytest
from pydantic import ValidationError

from ultimate_notion.blocks import Embed
from ultimate_notion.obj_api.blocks import Embed as ObjEmbed
from ultimate_notion.obj_api.blocks import EmbedTypeData, Page
from ultimate_notion.obj_api.core import extract_id
from ultimate_notion.obj_api.endpoints import NotionAPI
from ultimate_notion.obj_api.iterator import EndpointIterator
from ultimate_notion.obj_api.query import DataSourceQuery, DataSourceQueryBuilder
from ultimate_notion.session import Session


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for existing-behavior tests."""


@pytest.mark.parametrize(
    'url',
    [
        'https://example.com/p/59833787-2cf9-4fdf-8782-e53db20768a5',
        'https://app.notion.com.example.com/p/59833787-2cf9-4fdf-8782-e53db20768a5',
        'https://user@app.notion.com/p/59833787-2cf9-4fdf-8782-e53db20768a5',
        'http://app.notion.com/p/59833787-2cf9-4fdf-8782-e53db20768a5',
        'https://app.notion.com/p/not-a-page#598337872cf94fdf8782e53db20768a5',
        'https://[invalid',
    ],
)
def test_unrelated_or_invalid_notion_urls(url: str) -> None:
    assert extract_id(url) is None


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


def test_read_embed_signed_url() -> None:
    embed = Embed.wrap_obj_ref(ObjEmbed.model_validate({'embed': {'url': 'https://example.com/signed?token=abc'}}))
    assert embed.url == 'https://example.com/signed?token=abc'


@pytest.mark.parametrize('url', [None, 'https://example.com/chart'])
def test_invalid_embed_sources(url: str | None) -> None:
    data: dict[str, object] = {'url': url}
    if url is not None:
        data['file_upload'] = {'id': '59833787-2cf9-4fdf-8782-e53db20768a5'}
    with pytest.raises(ValidationError):
        EmbedTypeData.model_validate(data)


@pytest.mark.parametrize('multipart', [False, True])
def test_explicit_upload_mime_override(monkeypatch: pytest.MonkeyPatch, *, multipart: bool) -> None:
    monkeypatch.setattr('ultimate_notion.session.MAX_FILE_SIZE', 4 if multipart else 8)
    upload_data = {
        'object': 'file_upload',
        'id': '59833787-2cf9-4fdf-8782-e53db20768a5',
        'created_time': '2026-01-01T00:00:00Z',
        'last_edited_time': '2026-01-01T00:00:00Z',
        'status': 'uploaded',
        'filename': 'image.png',
        'content_type': 'image/jpeg',
        'created_by': {'object': 'user', 'id': '11111111-1111-4111-8111-111111111111', 'type': 'person', 'person': {}},
    }
    client = MagicMock()
    client.file_uploads.create.return_value = upload_data
    client.file_uploads.send.return_value = upload_data
    client.file_uploads.complete.return_value = upload_data
    session = Session.__new__(Session)
    session.api = NotionAPI(client)

    result = session.upload(BytesIO(b'abcdef'), file_name='image.png', mime_type='image/jpeg')

    creation = client.file_uploads.create.call_args.kwargs
    assert creation['filename'] == 'image.png'
    assert creation['content_type'] == 'image/jpeg'
    assert creation['mode'] == ('multi_part' if multipart else 'single_part')
    assert client.file_uploads.send.call_count == (2 if multipart else 1)
    for call in client.file_uploads.send.call_args_list:
        assert call.kwargs['file'][0] == 'image.png'
        assert call.kwargs['file'][2] == 'image/jpeg'
    assert client.file_uploads.complete.call_count == int(multipart)
    assert result.content_type == 'image/jpeg'

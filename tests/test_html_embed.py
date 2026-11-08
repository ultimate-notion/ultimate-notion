from __future__ import annotations

import json
from io import BytesIO
from typing import Any
from uuid import UUID

import httpx
import notion_client
import pytest
from pydantic import ConfigDict, ValidationError

from tests._file_upload_vcr import FILE_UPLOAD_QUERY_PARAMS, redact_file_response
from ultimate_notion.blocks import Embed
from ultimate_notion.file import UploadedFile
from ultimate_notion.obj_api.blocks import EmbedTypeData
from ultimate_notion.obj_api.objects import FileUpload
from ultimate_notion.page import Page
from ultimate_notion.session import Session

UPLOAD_ID = UUID('59833787-2cf9-4fdf-8782-e53db20768a5')


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for embed request tests."""


def _uploaded_html() -> UploadedFile:
    return UploadedFile.from_file_upload(
        FileUpload.model_validate(
            {
                'id': str(UPLOAD_ID),
                'created_time': '2026-01-01T00:00:00Z',
                'last_edited_time': '2026-01-01T00:00:00Z',
                'status': 'uploaded',
                'filename': 'chart.html',
                'content_type': 'text/html',
                'created_by': {'object': 'user', 'id': str(UPLOAD_ID), 'type': 'person', 'person': {}},
            }
        )
    )


def test_uploaded_html_embed_and_source_replacement() -> None:
    uploaded = _uploaded_html()
    embed = Embed(uploaded, caption='Interactive chart')
    payload = embed.obj_ref.serialize_for_api()['embed']
    assert payload['type'] == 'file_upload'
    assert payload['file_upload'] == {'id': str(UPLOAD_ID)}
    assert 'url' not in payload
    assert embed.url is None
    assert embed.caption is not None and str(embed.caption) == 'Interactive chart'

    embed.url = 'https://example.com/chart'
    payload = embed.obj_ref.serialize_for_api()['embed']
    assert payload['url'] == 'https://example.com/chart'
    assert 'file_upload' not in payload
    assert 'type' not in payload
    assert embed.set_file_upload(uploaded) is embed
    assert embed.obj_ref.serialize_for_api()['embed']['file_upload'] == {'id': str(UPLOAD_ID)}


def test_html_embed_append_update_and_refresh() -> None:
    requests: list[dict[str, Any]] = []
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method != 'GET':
            requests.append(json.loads(request.content))
        block = {
            'object': 'block',
            'id': str(UPLOAD_ID),
            'type': 'embed',
            'embed': {'url': f'https://example.com/html?signature={len(calls)}', 'caption': []},
        }
        if request.url.path.endswith('/children'):
            return httpx.Response(
                200,
                json={
                    'object': 'list',
                    'type': 'block',
                    'block': {},
                    'results': [block],
                    'has_more': False,
                    'next_cursor': None,
                },
            )
        return httpx.Response(200, json=block)

    client = notion_client.Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(handle)))
    uploaded = _uploaded_html()
    with Session(client=client) as session:
        embed = Embed(uploaded)
        session.api.blocks.children.append(UPLOAD_ID, [embed.obj_ref])
        assert embed.url == 'https://example.com/html?signature=1'
        embed.set_file_upload(uploaded)
        assert embed.url == 'https://example.com/html?signature=2'
        embed.reload()
        assert embed.url == 'https://example.com/html?signature=3'

    assert [call.method for call in calls] == ['PATCH', 'PATCH', 'GET']
    assert requests[0]['children'][0]['embed']['file_upload'] == {'id': str(UPLOAD_ID)}
    assert requests[1]['embed']['file_upload'] == {'id': str(UPLOAD_ID)}
    assert 'url' not in requests[1]['embed']
    assert 'type' not in requests[1]['embed']


def test_file_upload_source_validation() -> None:
    source = {'type': 'file_upload', 'file_upload': {'id': str(UPLOAD_ID)}}
    assert EmbedTypeData.model_validate(source).serialize_for_api() == {'caption': [], **source}


def test_ambiguous_embed_sources_rejected_with_lenient_parsing() -> None:
    class LenientEmbed(EmbedTypeData):
        model_config = ConfigDict(extra='ignore')

    with pytest.raises(ValidationError):
        LenientEmbed.model_validate({'url': 'https://example.com/chart', 'file_upload': {'id': str(UPLOAD_ID)}})


@pytest.mark.vcr(filter_query_parameters=FILE_UPLOAD_QUERY_PARAMS, before_record_response=redact_file_response)
def test_uploaded_html_round_trip(notion: Session, root_page: Page) -> None:
    page = notion.create_page(parent=root_page, title='Uploaded HTML embed round trip')
    try:
        first = notion.upload(
            BytesIO(b'<!doctype html><html><body>First embedded document</body></html>'),
            file_name='first.html',
            mime_type='text/html',
        )
        first.wait_until_uploaded()
        embed = Embed(first, caption='Interactive document')
        page.append(embed)
        embed.reload()
        assert embed.caption is not None and str(embed.caption) == 'Interactive document'
        assert embed.url is not None
        original = httpx.get(embed.url)
        original.raise_for_status()
        assert 'First embedded document' in original.text

        replacement = notion.upload(
            BytesIO(b'<!doctype html><html><body>Replacement embedded document</body></html>'),
            file_name='replacement.html',
            mime_type='text/html',
        )
        replacement.wait_until_uploaded()
        embed.set_file_upload(replacement)
        embed.reload()
        assert embed.url is not None
        updated = httpx.get(embed.url)
        updated.raise_for_status()
        assert 'Replacement embedded document' in updated.text
        assert embed.caption is not None and str(embed.caption) == 'Interactive document'
    finally:
        page.delete()

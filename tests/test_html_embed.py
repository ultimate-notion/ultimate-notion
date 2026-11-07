from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import httpx
import notion_client
import pytest
from pydantic import ValidationError

from ultimate_notion.blocks import Embed
from ultimate_notion.file import UploadedFile
from ultimate_notion.obj_api.blocks import Embed as ObjEmbed
from ultimate_notion.obj_api.blocks import EmbedTypeData
from ultimate_notion.obj_api.objects import FileUpload
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


def test_read_html_embed_signed_url() -> None:
    embed = Embed.wrap_obj_ref(ObjEmbed.model_validate({'embed': {'url': 'https://example.com/signed?token=abc'}}))
    assert embed.url == 'https://example.com/signed?token=abc'


def test_html_embed_append_update_and_refresh() -> None:
    requests: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method != 'GET':
            requests.append(json.loads(request.content))
        block = {
            'object': 'block',
            'id': str(UPLOAD_ID),
            'type': 'embed',
            'embed': {'url': f'https://example.com/html?signature={len(requests)}', 'caption': []},
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
        assert embed.url == 'https://example.com/html?signature=2'

    assert requests[0]['children'][0]['embed']['file_upload'] == {'id': str(UPLOAD_ID)}
    assert requests[1]['embed']['file_upload'] == {'id': str(UPLOAD_ID)}
    assert 'url' not in requests[1]['embed']


@pytest.mark.parametrize('url', [None, 'https://example.com/chart'])
def test_embed_requires_exactly_one_source(url: str | None) -> None:
    data: dict[str, object] = {'url': url}
    if url is not None:
        data['file_upload'] = {'id': str(UPLOAD_ID)}
    with pytest.raises(ValidationError, match='exactly one'):
        EmbedTypeData.model_validate(data)

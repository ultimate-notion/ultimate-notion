from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

import pytest

from ultimate_notion.obj_api.endpoints import NotionAPI
from ultimate_notion.session import Session


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for isolated unit tests."""


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

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

import pytest

from ultimate_notion.obj_api.endpoints import NotionAPI
from ultimate_notion.session import Session


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for upload request tests."""


@pytest.mark.parametrize(
    ('filename', 'mime_type', 'expected'),
    [
        ('model.glb', 'application/octet-stream', 'application/octet-stream'),
        ('model.unknown-extension', None, 'application/octet-stream'),
        ('image.png', None, 'image/png'),
    ],
)
@pytest.mark.parametrize('multipart', [False, True])
def test_upload_mime_metadata(
    monkeypatch: pytest.MonkeyPatch, filename: str, mime_type: str | None, expected: str, *, multipart: bool
) -> None:
    monkeypatch.setattr('ultimate_notion.session.MAX_FILE_SIZE', 4 if multipart else 8)
    upload_data = {
        'object': 'file_upload',
        'id': '59833787-2cf9-4fdf-8782-e53db20768a5',
        'created_time': '2026-01-01T00:00:00Z',
        'last_edited_time': '2026-01-01T00:00:00Z',
        'status': 'uploaded',
        'filename': filename,
        'content_type': expected,
        'created_by': {'object': 'user', 'id': '11111111-1111-4111-8111-111111111111', 'type': 'person', 'person': {}},
    }
    client = MagicMock()
    client.file_uploads.create.return_value = upload_data
    client.file_uploads.send.return_value = upload_data
    client.file_uploads.complete.return_value = upload_data
    session = Session.__new__(Session)
    session.api = NotionAPI(client)

    result = session.upload(BytesIO(b'abcdef'), file_name=filename, mime_type=mime_type)

    creation = client.file_uploads.create.call_args.kwargs
    assert creation['filename'] == filename
    assert creation['content_type'] == expected
    assert creation['mode'] == ('multi_part' if multipart else 'single_part')
    assert client.file_uploads.send.call_count == (2 if multipart else 1)
    for call in client.file_uploads.send.call_args_list:
        assert call.kwargs['file'][0] == filename
        assert call.kwargs['file'][2] == expected
    assert client.file_uploads.complete.call_count == int(multipart)
    assert result.content_type == expected

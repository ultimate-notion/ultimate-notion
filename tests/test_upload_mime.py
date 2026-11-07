from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests._file_upload_vcr import FILE_UPLOAD_QUERY_PARAMS, redact_file_response
from ultimate_notion import Image, Page
from ultimate_notion.file import NotionFile
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


@pytest.mark.vcr(filter_query_parameters=FILE_UPLOAD_QUERY_PARAMS, before_record_response=redact_file_response)
def test_upload_generic_mime_round_trip(notion: Session, root_page: Page) -> None:
    page = notion.create_page(parent=root_page, title='Generic MIME upload round trip')
    try:
        content = Path('docs/assets/images/favicon.svg').read_bytes()
        with patch.object(
            notion.client.file_uploads, 'create', wraps=notion.client.file_uploads.create
        ) as create_upload:
            uploaded = notion.upload(BytesIO(content), file_name='image.svg', mime_type='application/octet-stream')
        assert create_upload.call_args.kwargs['content_type'] == 'application/octet-stream'
        uploaded.wait_until_uploaded()
        assert uploaded.content_type == 'image/svg+xml'

        page.append(Image(uploaded, caption='Detected image type'))
        page.reload()
        (image,) = page.children
        assert isinstance(image, Image)
        assert isinstance(image.file_info, NotionFile)
        assert image.caption is not None and str(image.caption) == 'Detected image type'
    finally:
        page.delete()

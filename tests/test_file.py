from __future__ import annotations

from pathlib import Path

import pytest

import ultimate_notion as uno


@pytest.mark.file_upload
def test_file_upload(root_page: uno.Page, notion: uno.Session, tmp_path: Path) -> None:
    with open('docs/assets/images/favicon.png', 'rb') as file:
        file_info = notion.upload(file=file)

    page = notion.create_page(parent=root_page, title='Test Page to test file uploads')
    page.icon = file_info

    # test a large 25mb file
    file_path = tmp_path / 'dummy'
    size = 25 * 1024 * 1024  # 25 MB

    # Create the file with the desired size efficiently
    with open(file_path, 'wb') as f:
        f.seek(size - 1)
        f.write(b'\0')

    assert file_path.stat().st_size == size

    with open(file_path, 'rb') as file:
        large_file_info = notion.upload(file=file)

    page.append(uno.File(large_file_info, caption='A large 25MB dummy file'))


@pytest.mark.file_upload
def test_import_url(root_page: uno.Page, notion: uno.Session) -> None:
    url = 'https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/Big_Buck_Bunny_1080_10s_20MB.mp4'
    uploaded_file = notion.import_url(url=url, file_name='bunny_movie.mp4')
    page = notion.create_page(parent=root_page, title='Test Page to import an url as file')
    page.append(uno.Video(uploaded_file, caption='An imported image from URL'))

    assert uploaded_file.file_name == 'bunny_movie.mp4'
    assert uploaded_file.file_import_result.status == 'success'
    assert uploaded_file.expiry_time is not None
    assert uploaded_file.status == uno.FileUploadStatus.UPLOADED
    assert uploaded_file.content_type == 'application/mp4'
    assert uploaded_file.content_length >= 20_000_000  # type: ignore[operator]


@pytest.mark.file_upload
def test_list_uploads(notion: uno.Session) -> None:
    before_uploads = notion.list_uploads()
    assert isinstance(before_uploads, list)

    with open('docs/assets/images/favicon.png', 'rb') as file:
        notion.upload(file=file)

    after_uploads = notion.list_uploads()
    assert len(after_uploads) == len(before_uploads) + 1

    url = 'https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/Big_Buck_Bunny_1080_10s_20MB.mp4'
    uploaded_file = notion.import_url(url=url, file_name='bunny_movie.mp4', block=False)
    uploads = notion.list_uploads(filter=uno.FileUploadStatus.PENDING)
    assert len([upload for upload in uploads if upload == uploaded_file]) == 1

    uploaded_file.wait_until_uploaded()
    uploads = notion.list_uploads(filter=uno.FileUploadStatus.UPLOADED)
    assert len([upload for upload in uploads if upload == uploaded_file]) == 1


@pytest.mark.file_upload
def test_upload_wav(notion: uno.Session, root_page: uno.Page) -> None:
    with open('tests/assets/sample-3s.wav', 'rb') as file:
        uploaded_file = notion.upload(file=file)

    assert uploaded_file.content_type == 'audio/wav'

    page = notion.create_page(parent=root_page, title='Test Page with a WAV file')
    page.append(uno.Audio(uploaded_file, caption='An uploaded WAV audio'))


@pytest.mark.file_upload
def test_upload_svg(notion: uno.Session, root_page: uno.Page) -> None:
    with open('docs/assets/images/favicon.svg', 'rb') as file:
        uploaded_file = notion.upload(file=file)

    assert uploaded_file.content_type == 'image/svg+xml'

    page = notion.create_page(parent=root_page, title='Test Page with an SVG file')
    page.append(uno.Image(uploaded_file, caption='An uploaded SVG image'))

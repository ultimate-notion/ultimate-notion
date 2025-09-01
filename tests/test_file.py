from __future__ import annotations

from pathlib import Path

import pytest

import ultimate_notion as uno


@pytest.mark.file_upload
def test_file_upload(root_page: uno.Page, notion: uno.Session, tmp_path: Path) -> None:
    with open('docs/assets/images/favicon.png', 'rb') as file:
        file_info = notion.upload(file=file)

    page = notion.create_page(parent=root_page, title='Test Page to check file upload as icon')
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

from __future__ import annotations

import pytest

import ultimate_notion as uno


@pytest.mark.file_upload
def test_file_upload(root_page: uno.Page, notion: uno.Session) -> None:
    with open('docs/assets/images/favicon.png', 'rb') as file:
        file_info = notion.upload(file=file)

    page = notion.create_page(parent=root_page, title='Test Page to check file upload as icon')
    page.icon = file_info

    # from IPython import embed

    # embed()  # for debugging

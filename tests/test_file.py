from __future__ import annotations

import pytest

import ultimate_notion as uno


@pytest.mark.vcr()
def test_file_upload(notion: uno.Session) -> None:
    with open('docs/assets/images/favicon.png', 'rb') as file:
        file_info = notion.upload(file=file)

    assert file_info is not None

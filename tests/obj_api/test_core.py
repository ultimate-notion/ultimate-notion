from __future__ import annotations

from uuid import UUID, uuid4

from ultimate_notion.obj_api.core import extract_id


def test_extract_id() -> None:
    """Make sure we can parse UUID's with and without dashes."""

    page_id = uuid4()

    assert UUID(extract_id(str(page_id))) == page_id

    for base_url in ('https://www.notion.so', 'https://notion.so'):
        page_url = f'{base_url}/{page_id}'
        assert UUID(extract_id(page_url)) == page_id

        page_url = f'{base_url}/page-title-{page_id}'
        assert UUID(extract_id(page_url)) == page_id

        block_id = uuid4()
        page_url = f'{base_url}/username/page-title-{page_id}#{block_id!s}'
        assert UUID(extract_id(page_url)) == block_id

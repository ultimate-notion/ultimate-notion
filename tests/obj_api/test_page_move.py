from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID

from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.endpoints import NotionAPI

PAGE_ID = UUID('11111111-1111-4111-8111-111111111111')
PARENT_ID = UUID('22222222-2222-4222-8222-222222222222')
NEW_PARENT_ID = UUID('33333333-3333-4333-8333-333333333333')


def _page_data(*, page_id: UUID = PAGE_ID, parent_id: UUID = PARENT_ID) -> dict[str, object]:
    return {
        'object': 'page',
        'id': str(page_id),
        'parent': {'type': 'page_id', 'page_id': str(parent_id)},
        'properties': {'title': {'id': 'title', 'type': 'title', 'title': []}},
    }


def test_move_page_updates_parent_for_partial_response() -> None:
    client = MagicMock()
    api = NotionAPI(client)
    page = obj_blocks.Page.model_validate(_page_data())
    new_parent = obj_blocks.Page.model_validate(_page_data(page_id=NEW_PARENT_ID))
    client.pages.move.return_value = {'object': 'page', 'id': str(PAGE_ID)}

    api.pages.move(page, new_parent)

    client.pages.move.assert_called_once_with(str(PAGE_ID), parent={'type': 'page_id', 'page_id': str(NEW_PARENT_ID)})
    assert page.parent == objs.PageRef(page_id=NEW_PARENT_ID)

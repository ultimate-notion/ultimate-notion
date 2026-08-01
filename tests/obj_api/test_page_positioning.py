from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID

import pytest

from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.endpoints import NotionAPI
from ultimate_notion.obj_api.enums import InsertPosition

PAGE_ID = UUID('11111111-1111-4111-8111-111111111111')
PARENT_ID = UUID('22222222-2222-4222-8222-222222222222')
ANCHOR_ID = UUID('33333333-3333-4333-8333-333333333333')


def _page_data(*, page_id: UUID = PAGE_ID, parent_id: UUID = PARENT_ID) -> dict[str, object]:
    return {
        'object': 'page',
        'id': str(page_id),
        'parent': {'type': 'page_id', 'page_id': str(parent_id)},
        'properties': {'title': {'id': 'title', 'type': 'title', 'title': []}},
    }


def _api() -> tuple[NotionAPI, MagicMock]:
    client = MagicMock()
    return NotionAPI(client), client


@pytest.mark.parametrize(
    ('position', 'expected'),
    [
        (InsertPosition.START, {'type': 'page_start'}),
        (InsertPosition.END, {'type': 'page_end'}),
    ],
)
def test_create_page_position(position: InsertPosition, expected: dict[str, str]) -> None:
    api, client = _api()
    client.pages.create.return_value = _page_data()
    parent = obj_blocks.Page.model_validate(_page_data(page_id=PARENT_ID))

    api.pages.create(parent, position=position)

    assert client.pages.create.call_args.kwargs['position'] == expected


def test_create_page_after_block() -> None:
    api, client = _api()
    client.pages.create.return_value = _page_data()
    parent = obj_blocks.Page.model_validate(_page_data(page_id=PARENT_ID))
    anchor = obj_blocks.Paragraph.model_construct(id=ANCHOR_ID)

    api.pages.create(parent, after=anchor)

    assert client.pages.create.call_args.kwargs['position'] == {
        'type': 'after_block',
        'after_block': {'id': str(ANCHOR_ID)},
    }


def test_create_page_rejects_two_positions() -> None:
    api, _ = _api()
    parent = obj_blocks.Page.model_validate(_page_data(page_id=PARENT_ID))
    anchor = obj_blocks.Paragraph.model_construct(id=ANCHOR_ID)

    with pytest.raises(ValueError, match='mutually exclusive'):
        api.pages.create(parent, after=anchor, position=InsertPosition.START)


def test_prepend_block_children() -> None:
    api, client = _api()
    block = obj_blocks.Paragraph.model_construct(id=PAGE_ID)
    client.blocks.children.append.return_value = {
        'object': 'list',
        'type': 'block',
        'block': {},
        'results': [block.serialize_for_api()],
        'has_more': False,
        'next_cursor': None,
    }

    api.blocks.children.append(PARENT_ID, [block], position=InsertPosition.START)

    assert client.blocks.children.append.call_args.kwargs['position'] == {'type': 'start'}


def test_move_page_updates_parent_for_partial_response() -> None:
    api, client = _api()
    page = obj_blocks.Page.model_validate(_page_data())
    new_parent = obj_blocks.Page.model_validate(_page_data(page_id=ANCHOR_ID))
    client.pages.move.return_value = {'object': 'page', 'id': str(PAGE_ID)}

    api.pages.move(page, new_parent)

    client.pages.move.assert_called_once_with(str(PAGE_ID), parent={'type': 'page_id', 'page_id': str(ANCHOR_ID)})
    assert page.parent == objs.PageRef(page_id=ANCHOR_ID)


@pytest.mark.parametrize('position', [InsertPosition.START, InsertPosition.END])
def test_insert_markdown_position(position: InsertPosition) -> None:
    api, client = _api()
    client.pages.update_markdown.return_value = {'object': 'page_markdown', 'id': str(PAGE_ID)}

    api.pages.insert_markdown(PAGE_ID, '# New content', position=position)

    client.pages.update_markdown.assert_called_once_with(
        str(PAGE_ID),
        type='insert_content',
        insert_content={'content': '# New content', 'position': {'type': position.value}},
    )


def test_insert_markdown_after_selection() -> None:
    api, client = _api()
    client.pages.update_markdown.return_value = {'object': 'page_markdown', 'id': str(PAGE_ID)}

    api.pages.insert_markdown(PAGE_ID, 'New content', after='Start...end')

    client.pages.update_markdown.assert_called_once_with(
        str(PAGE_ID),
        type='insert_content',
        insert_content={'content': 'New content', 'after': 'Start...end'},
    )


def test_insert_markdown_rejects_two_positions() -> None:
    api, _ = _api()

    with pytest.raises(ValueError, match='mutually exclusive'):
        api.pages.insert_markdown(PAGE_ID, 'content', after='text', position=InsertPosition.START)

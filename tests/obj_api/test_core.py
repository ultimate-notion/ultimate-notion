from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from ultimate_notion.obj_api.blocks import Page, Paragraph
from ultimate_notion.obj_api.core import extract_id
from ultimate_notion.obj_api.objects import Bot, BuiltInIconObject, Person, User


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable the live Notion cleanup fixture for pure object parsing tests."""


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


def test_user_object_default_propagates_to_subtypes() -> None:
    """The `object='user'` default must be inherited by generic `User` subtypes.

    pydantic >=2.13 stopped propagating mutated `model_fields` defaults through generic
    parameterizations, which broke parsing of Notion people properties.
    See: https://github.com/ultimate-notion/ultimate-notion/issues/189
    """
    assert User.model_fields['object'].default == 'user'
    assert Person.model_fields['object'].default == 'user'
    assert Bot.model_fields['object'].default == 'user'

    person = Person.model_validate(
        {
            'object': 'user',
            'id': '00000000-0000-0000-0000-000000000000',
            'type': 'person',
            'name': 'Alice',
            'person': {'email': 'alice@example.com'},
        }
    )
    assert person.object == 'user'


def test_paragraph_accepts_null_icon() -> None:
    paragraph = Paragraph.model_validate(
        {
            'object': 'block',
            'type': 'paragraph',
            'paragraph': {
                'rich_text': [],
                'color': 'default',
                'children': [],
                'icon': None,
            },
        }
    )

    assert paragraph.paragraph.icon is None


def test_page_accepts_built_in_icon() -> None:
    """A page with a built-in (icon gallery) icon must round-trip, see issue #295.

    The Notion API returns these as `{'type': 'icon', 'icon': {'name': ..., 'color': ...}}`,
    which previously failed validation and cascaded into search/list endpoints.
    """
    page = Page.model_validate(
        {
            'object': 'page',
            'id': '00000000-0000-0000-0000-000000000000',
            'created_time': '2024-01-01T00:00:00.000Z',
            'last_edited_time': '2024-01-01T00:00:00.000Z',
            'archived': False,
            'in_trash': False,
            'icon': {'type': 'icon', 'icon': {'name': 'snake', 'color': 'purple'}},
            'cover': None,
            'parent': {'type': 'workspace', 'workspace': True},
            'url': 'https://www.notion.so/00000000000000000000000000000000',
            'properties': {},
        }
    )

    assert isinstance(page.icon, BuiltInIconObject)
    assert page.icon.icon.name == 'snake'
    assert page.icon.icon.color == 'purple'


def test_block_serialization_omits_read_only_archive_flags() -> None:
    data = Paragraph.build(paragraph={'rich_text': []}).serialize_for_api()

    assert 'has_children' not in data
    assert 'in_trash' not in data
    assert 'archived' not in data
    assert 'is_archived' not in data

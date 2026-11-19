from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from ultimate_notion.database import Database as DatabaseWrapper
from ultimate_notion.emoji import BuiltInIcon
from ultimate_notion.obj_api.blocks import Database, Page, Paragraph
from ultimate_notion.obj_api.core import ObjectRef, UniqueObject, Unset, UserRef, extract_id
from ultimate_notion.obj_api.endpoints import DatabasesEndpoint
from ultimate_notion.obj_api.objects import Bot, BuiltInIconObject, Person, User
from ultimate_notion.obj_api.props import Number, NumberPropertyItem, PropertyItem


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


@pytest.mark.parametrize('host', ['app.notion.com', 'notion.com', 'www.notion.com', 'notion.so', 'www.notion.so'])
@pytest.mark.parametrize('compact', [False, True])
def test_current_notion_url_references(host: str, *, compact: bool) -> None:
    page_id = UUID('59833787-2cf9-4fdf-8782-e53db20768a5')
    block_id = UUID('c02fc1d3-db8b-45c5-a222-27595b15aea7')
    page_text = page_id.hex if compact else str(page_id)
    url = f'https://{host}/p/{page_text}?source=copy_link'

    assert ObjectRef.build(url).id == page_id
    assert ObjectRef.build(f'{url}#{block_id.hex}').id == block_id


def test_rejects_lookalike_notion_host() -> None:
    assert extract_id('https://notionXso/59833787-2cf9-4fdf-8782-e53db20768a5') is None


def test_uppercase_notion_block_url() -> None:
    url = 'https://APP.NOTION.COM/p/598337872CF94FDF8782E53DB20768A5#C02FC1D3DB8B45C5A22227595B15AEA7'
    assert ObjectRef.build(url).id == UUID('c02fc1d3-db8b-45c5-a222-27595b15aea7')


def test_model_id_defaults_and_property_item_round_trip() -> None:
    object_id = UUID('00000000-0000-0000-0000-000000000001')
    assert UniqueObject.model_validate({'id': str(object_id)}).id == object_id
    assert UniqueObject().id is Unset
    assert Number(number=1).id is Unset
    assert Number(number=1).serialize_for_api() == {'type': 'number', 'number': 1}

    payload = {'object': 'property_item', 'type': 'number', 'id': 'abc', 'number': 1}
    item = PropertyItem.model_validate(payload)
    assert isinstance(item, NumberPropertyItem)
    assert item.id == 'abc'
    assert item.serialize_for_api() == payload


def test_references_and_property_items_require_ids() -> None:
    with pytest.raises(ValidationError, match='id'):
        UserRef.model_validate({})
    with pytest.raises(ValidationError, match='id'):
        NumberPropertyItem.model_validate({'number': 1})


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


def test_database_accepts_built_in_icon() -> None:
    """A database with a built-in icon must validate, see issue #431."""
    database = Database.model_validate(
        {
            'object': 'database',
            'id': '00000000-0000-0000-0000-000000000000',
            'icon': {'type': 'icon', 'icon': {'name': 'table', 'color': 'purple'}},
        }
    )

    assert isinstance(database.icon, BuiltInIconObject)
    assert database.icon.icon.name == 'table'
    assert database.icon.icon.color == 'purple'

    wrapped_database = DatabaseWrapper.wrap_obj_ref(database)
    assert isinstance(wrapped_database.icon, BuiltInIcon)
    assert wrapped_database.icon.name == 'table'
    assert wrapped_database.icon.color == 'purple'


def test_database_icon_request_serialization() -> None:
    """Writable database icons serialize into the create/update request shape."""
    icon = BuiltInIcon('table', color='blue')

    assert DatabasesEndpoint._build_request(icon=icon.obj_ref) == {
        'icon': {'type': 'icon', 'icon': {'name': 'table', 'color': 'blue'}}
    }
    assert DatabasesEndpoint._build_request() == {}


def test_block_serialization_omits_read_only_archive_flags() -> None:
    data = Paragraph.build(paragraph={'rich_text': []}).serialize_for_api()

    assert 'has_children' not in data
    assert 'in_trash' not in data
    assert 'archived' not in data
    assert 'is_archived' not in data


@pytest.mark.parametrize(
    'url',
    [
        'https://example.com/p/59833787-2cf9-4fdf-8782-e53db20768a5',
        'https://app.notion.com.example.com/p/59833787-2cf9-4fdf-8782-e53db20768a5',
        'https://user@app.notion.com/p/59833787-2cf9-4fdf-8782-e53db20768a5',
        'http://app.notion.com/p/59833787-2cf9-4fdf-8782-e53db20768a5',
        'https://app.notion.com/p/not-a-page#598337872cf94fdf8782e53db20768a5',
        'https://[invalid',
    ],
)
def test_unrelated_or_invalid_notion_urls(url: str) -> None:
    assert extract_id(url) is None

from __future__ import annotations

from uuid import UUID, uuid4

from ultimate_notion.obj_api.core import extract_id
from ultimate_notion.obj_api.objects import Bot, Person, User


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

"""Tests for Custom Agent identity and write payloads."""

from __future__ import annotations

from uuid import UUID

import pytest

import ultimate_notion as uno
from ultimate_notion.obj_api.objects import MentionObject
from ultimate_notion.obj_api.props import People
from ultimate_notion.props import Person
from ultimate_notion.rich_text import Text
from ultimate_notion.user import Bot

AGENT_ID = 'ef82a3bc-58dc-47ca-8ab6-56d144d166cc'
BOT_ID = '9188c6a5-7381-452f-b3dc-d4865aa89bdf'


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """These payload tests use synthetic agents."""


@pytest.mark.parametrize('agent_or_bot_id', [AGENT_ID, BOT_ID])
def test_custom_agent_reference_writes(agent_or_bot_id: str) -> None:
    agent = uno.CustomAgentRef(agent_or_bot_id)
    reference = {'id': agent_or_bot_id, 'object': 'user'}
    assert Person(agent).obj_ref.serialize_for_api() == {'people': [reference], 'type': 'people'}
    (mention,) = uno.mention(agent).obj_ref
    assert mention.serialize_for_api()['mention'] == {'type': 'user', 'user': reference}


def test_custom_agent_identity_is_preserved_on_read() -> None:
    inline = {'object': 'user', 'type': 'bot', 'id': BOT_ID, 'agent_id': AGENT_ID, 'name': 'Example agent'}
    people = People.model_validate({'people': [inline]})
    (assigned_agent,) = Person.wrap_obj_ref(People.model_validate(people.model_dump())).value

    mention = MentionObject.model_validate(
        {'type': 'mention', 'mention': {'type': 'user', 'user': inline}, 'plain_text': '@Example agent'}
    )
    (wrapped_mention,) = Text.wrap_obj_ref([mention]).mentions
    for user in (assigned_agent, wrapped_mention.user):
        assert isinstance(user, Bot)
        assert user.id == UUID(BOT_ID)
        assert user.agent_id == UUID(AGENT_ID)
        assert user.name == 'Example agent'

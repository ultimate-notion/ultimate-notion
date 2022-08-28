"""Unit tests for the Notional user objects."""

import pytest

from ultimate_notion.core.user import Bot, Person, User

ALICE = """{
  "type": "person",
  "object": "user",
  "id": "fb187a7b-547c-47b0-a575-8dc15b02138b",
  "name": "Alice",
  "avatar_url": "https://static.wikia.nocookie.net/disney/images/7/75/Profile_-_Alice.jpeg",
  "person": {
    "email": "nobody@null.com"
  }
}"""  # noqa: E501

BOB = """{
  "type": "bot",
  "object": "user",
  "id": "baa4465c-9760-4907-9939-4f080bb7ea43",
  "name": "Bob",
  "avatar_url": null,
  "bot": {}
}"""


def test_parse_alice():
    """Create a standard user from API data."""
    user = User.parse_raw(ALICE)

    assert type(user) == Person
    assert user.name == "Alice"


def test_parse_bob():
    """Create a bot user from API data."""
    user = User.parse_raw(BOB)

    assert type(user) == Bot
    assert user.name == "Bob"
    assert user.avatar_url is None


@pytest.mark.vcr()
def test_user_list(notion):
    """Confirm that we can list some users."""
    num_users = 0

    for orig in notion.users.list():
        dup = notion.users.retrieve(orig.id)
        assert orig == dup
        num_users += 1

    assert num_users > 0


@pytest.mark.vcr()
def test_me_bot(notion):
    """Verify that the current user looks valid."""
    me = notion.users.me()

    assert me is not None
    assert isinstance(me, Bot)

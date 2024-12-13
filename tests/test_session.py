"""Unit tests for the Notion Session"""

from __future__ import annotations

import pytest

import ultimate_notion as uno

from .conftest import CONTACTS_DB


@pytest.mark.vcr()
def test_raise_for_status(notion: uno.Session):
    notion.raise_for_status()


@pytest.mark.vcr()
def test_search_get_db(notion: uno.Session):
    db_by_name = notion.search_db(CONTACTS_DB).item()
    assert db_by_name.title == CONTACTS_DB

    db_by_id = notion.get_db(db_by_name.id)
    assert db_by_id.id == db_by_name.id


@pytest.mark.vcr()
def test_whoami_get_user(notion: uno.Session):
    me = notion.whoami()
    assert me.name == 'Github Unittests'
    user = notion.get_user(me.id)
    assert user.id == me.id
    user = notion.get_user(me.id, use_cache=False, raise_on_unknown=False)
    assert user.name == 'Github Unittests'
    with pytest.raises(uno.UnknownUserError):
        unknown_id = 'f3f2e850-b5d4-11ef-ac7e-96584d5248b2'
        notion.get_user(unknown_id, use_cache=False)


@pytest.mark.vcr()
def test_get_page_by_id(notion: uno.Session, intro_page: uno.Page):
    page_by_id = notion.get_page(intro_page.id)
    assert page_by_id.title == 'Getting Started'
    assert page_by_id == intro_page
    with pytest.raises(uno.UnknownPageError):
        unknown_id = 'f3f2e850-b5d4-11ef-ac7e-96584d5248b2'
        notion.get_page(unknown_id)


@pytest.mark.vcr()
def test_all_users(notion: uno.Session):
    users = notion.all_users()
    me = notion.whoami()
    assert me in users

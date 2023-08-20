"""Unit tests for the Notion Session"""
import pytest


@pytest.mark.webtest
def test_raise_for_status(notion):
    notion.raise_for_status()


@pytest.mark.webtest
def test_search_get_db(notion):
    db_by_name = notion.search_db('Contacts').item()
    assert db_by_name.title == 'Contacts'

    db_by_id = notion.get_db(db_by_name.id)
    assert db_by_id.id == db_by_name.id


@pytest.mark.webtest
def test_get_page(notion):
    page_id = 'e9f53dc380ce4a979424659ef13a0d2e'
    page = notion.get_page(page_id)
    assert page.title.value == 'ACME Template'


@pytest.mark.webtest
def test_whoami_get_user(notion):
    me = notion.whoami()
    assert me.name == 'Github Unittests'
    user = notion.get_user(me.id)
    assert user.id == me.id


@pytest.mark.webtest
def test_all_users(notion):
    users = notion.all_users()
    me = notion.whoami()
    assert me in users

"""Unit tests for the Notion Session"""

from __future__ import annotations

import pytest

import ultimate_notion as uno
from ultimate_notion.errors import UnknownPageError, UnknownUserError

from .conftest import CONTACTS_DB


@pytest.mark.vcr()
def test_raise_for_status(notion: uno.Session) -> None:
    notion.raise_for_status()


@pytest.mark.vcr()
def test_search_get_db(notion: uno.Session) -> None:
    db_by_name = notion.search_ds(CONTACTS_DB).item()
    assert db_by_name.title == CONTACTS_DB

    db_by_id = notion.get_ds(db_by_name.id)
    assert db_by_id.id == db_by_name.id


@pytest.mark.vcr()
def test_whoami_get_user(notion: uno.Session) -> None:
    me = notion.whoami()
    assert me.name == 'Github Unittests'
    user = notion.get_user(me.id)
    assert user.id == me.id
    user = notion.get_user(me.id, use_cache=False, raise_on_unknown=False)
    assert user.name == 'Github Unittests'
    notion.get_user('645e79dd-3e43-40de-9d51-39357c1c427f', use_cache=False)
    with pytest.raises(UnknownUserError):
        unknown_id = '745e79dd-3e43-40de-9d51-39357c1c428f'
        notion.get_user(unknown_id, use_cache=False)


@pytest.mark.vcr()
def test_get_page_by_id(notion: uno.Session, intro_page: uno.Page) -> None:
    page_by_id = notion.get_page(intro_page.id)
    assert page_by_id.title == 'Getting Started'
    assert page_by_id == intro_page
    with pytest.raises(UnknownPageError):
        unknown_id = '7855b161-f63e-4683-b7c7-8ca6e97ee266'
        notion.get_page(unknown_id)


@pytest.mark.vcr()
def test_all_users(notion: uno.Session) -> None:
    users = notion.all_users()
    me = notion.whoami()
    assert me in users


@pytest.mark.vcr()
def test_create_page(notion: uno.Session, root_page: uno.Page) -> None:
    notion_cover_url = 'https://www.notion.so/images/page-cover/woodcuts_2.jpg'
    cover_page = notion.create_page(
        parent=root_page,
        title='My new page created with a cover',
        cover=uno.url(notion_cover_url),
    )
    assert isinstance(cover_page.cover, uno.AnyFile)
    assert cover_page.cover == uno.ExternalFile(url=notion_cover_url)

    emoji_icon = '🐍'
    icon_page = notion.create_page(
        parent=root_page,
        title='My new page created with an icon',
        icon=emoji_icon,
    )
    assert isinstance(icon_page.icon, uno.Emoji)
    assert icon_page.icon == emoji_icon

from __future__ import annotations

import pytest

import ultimate_notion as uno
from ultimate_notion.obj_api import objects
from ultimate_notion.props import Title


@pytest.mark.vcr()
def test_retrieve_property(all_props_db: uno.Database) -> None:
    page = all_props_db.get_all_pages().to_pages()[0]
    page_obj = page.obj_ref
    page_props = page.props._obj_prop_vals
    notion = uno.Session.get_or_create()

    for _, prop_val in page_props.items():
        list(notion.api.pages.properties.retrieve(page_obj, prop_val))


@pytest.mark.vcr()
def test_create_page(
    notion: uno.Session,
    contacts_db: uno.Database,
    root_page: uno.Page,
) -> None:
    props_page = notion.api.pages.create(
        parent=contacts_db.obj_ref,
        title=Title('My new page created with properties by obj_api').obj_ref,
        properties={
            name: contacts_db.schema.get_prop(name).prop_value(value).obj_ref
            for name, value in (('Name', 'John Doe'), ('Role', None))
        },
    )
    assert props_page.properties['Name'].value == 'John Doe'
    assert props_page.properties['Role'].value is None

    notion_cover_url = 'https://www.notion.so/images/page-cover/woodcuts_2.jpg'
    cover_page = notion.api.pages.create(
        parent=root_page.obj_ref,
        title=Title('My new page created with a cover by obj_api').obj_ref,
        cover=uno.url(notion_cover_url).obj_ref,
    )
    assert isinstance(cover_page.cover, objects.FileObject)
    assert cover_page.cover == uno.ExternalFile(url=notion_cover_url).obj_ref

    emoji_icon = '🐍'
    icon_page = notion.api.pages.create(
        parent=root_page.obj_ref,
        title=Title('My new page created with an icon by obj_api').obj_ref,
        icon=uno.Emoji(emoji_icon).obj_ref,
    )
    assert isinstance(icon_page.icon, objects.EmojiObject)
    assert icon_page.icon == objects.EmojiObject.build(emoji_icon)


@pytest.mark.vcr()
def test_update_page(notion: uno.Session, contacts_db: uno.Database) -> None:
    page = notion.api.pages.create(
        parent=contacts_db.obj_ref,
        title=Title('My new page created by obj_api').obj_ref,
    )

    notion.api.pages.update(
        page,
        properties={
            name: contacts_db.schema.get_prop(name).prop_value(value).obj_ref
            for name, value in (('Name', 'John Doe'), ('Role', None))
        },
    )
    assert page.properties['Name'].value == 'John Doe'
    assert page.properties['Role'].value is None

    notion_cover_url = 'https://www.notion.so/images/page-cover/woodcuts_2.jpg'
    notion.api.pages.update(page, cover=uno.url(notion_cover_url).obj_ref)
    assert isinstance(page.cover, objects.FileObject)
    assert page.cover == uno.ExternalFile(url=notion_cover_url).obj_ref

    emoji_icon = '🐍'
    notion.api.pages.update(page, icon=uno.Emoji(emoji_icon).obj_ref)
    assert isinstance(page.icon, objects.EmojiObject)
    assert page.icon == objects.EmojiObject.build(emoji_icon)

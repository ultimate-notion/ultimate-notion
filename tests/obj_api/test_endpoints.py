from __future__ import annotations

import pytest

import ultimate_notion as uno
from ultimate_notion.obj_api import objects, props
from ultimate_notion.props import Title


@pytest.mark.vcr()
def test_retrieve_property(notion: uno.Session, all_props_db: uno.Database) -> None:
    page = all_props_db.get_all_pages().to_pages()[0]
    page_obj = page.obj_ref
    page_props = page.props._obj_prop_vals

    for _, prop_val in page_props.items():
        list(notion.api.pages.properties.retrieve(page_obj, prop_val))


@pytest.mark.vcr()
def test_create_page(notion: uno.Session, root_page: uno.Page) -> None:
    class ContactsDB(uno.Schema):
        name = uno.PropType.Title('Name')
        role = uno.PropType.Text('Role')

    contacts_db = notion.create_db(
        parent=root_page, title='Contacts DB for low-level page creation test', schema=ContactsDB
    )

    props_page = notion.api.pages.create(
        parent=contacts_db.obj_ref,
        title=Title('John Doe').obj_ref,
        properties={'Role': props.RichText.build(uno.text('Carpenter').obj_ref)},
    )
    assert props_page.properties['Name'].value[0].plain_text == 'John Doe'
    assert props_page.properties['Role'].value[0].plain_text == 'Carpenter'

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
def test_update_page(notion: uno.Session, root_page: uno.Page) -> None:
    class ContactsDB(uno.Schema):
        name = uno.PropType.Title('Name')
        role = uno.PropType.Text('Role')

    contacts_db = notion.create_db(
        parent=root_page, title='Contacts DB for low-level page update test', schema=ContactsDB
    )

    page = notion.api.pages.create(
        parent=contacts_db.obj_ref,
        title=Title('My new page created by obj_api').obj_ref,
    )
    assert page.properties['Role'].value == []
    notion.api.pages.update(page, properties={'Role': props.RichText.build(uno.text('Carpenter').obj_ref)})
    assert page.properties['Role'].value[0].plain_text == 'Carpenter'

    notion_cover_url = 'https://www.notion.so/images/page-cover/woodcuts_2.jpg'
    notion.api.pages.update(page, cover=uno.url(notion_cover_url).obj_ref)
    assert isinstance(page.cover, objects.FileObject)
    assert page.cover == uno.ExternalFile(url=notion_cover_url).obj_ref

    emoji_icon = '🐍'
    notion.api.pages.update(page, icon=uno.Emoji(emoji_icon).obj_ref)
    assert isinstance(page.icon, objects.EmojiObject)
    assert page.icon == objects.EmojiObject.build(emoji_icon)

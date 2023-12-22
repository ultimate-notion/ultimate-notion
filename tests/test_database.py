"""
`# type: ignore` are mostly do to mypy's too strict way of handling the type of property getters and setters.
More details here: https://github.com/python/mypy/issues/3004
"""

from __future__ import annotations

import pytest

from ultimate_notion import Database, Page, RichText, Session, schema

from .conftest import CONTACTS_DB


def test_schema(article_db: Database):
    ref_schema = article_db.schema
    assert article_db.title == 'Articles'

    assert issubclass(ref_schema, schema.PageSchema)
    db_schema = {
        'Name': schema.Title(),
        'Cost': schema.Number(schema.NumberFormat.DOLLAR),
        'Description': schema.Text(),
    }
    assert ref_schema.to_dict() == db_schema

    class MySchema(schema.PageSchema, db_title='My Schema'):
        name = schema.Column('Name', schema.Title())
        cost = schema.Column('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Column('Description', schema.Text())

    article_db.schema = MySchema

    class WrongSchema(schema.PageSchema, db_title='My Wrong Schema'):
        name = schema.Column('Name', schema.Title())
        cost = schema.Column('Cost', schema.Text())
        desc = schema.Column('Description', schema.Text())

    with pytest.raises(schema.SchemaError):
        article_db.schema = WrongSchema


def test_db_without_title(notion: Session, root_page: Page):
    """Simple database of articles"""

    class Article(schema.PageSchema, db_title=None):
        name = schema.Column('Name', schema.Title())
        cost = schema.Column('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Column('Description', schema.Text())

    db = notion.create_db(parent=root_page, schema=Article)
    assert db.title == ''
    assert db.description == ''
    db.delete()


def test_db_with_docstring(notion: Session, root_page: Page):
    """Simple database of articles"""

    class Article(schema.PageSchema, db_title=None):
        """My articles"""

        name = schema.Column('Name', schema.Title())
        cost = schema.Column('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Column('Description', schema.Text())

    db = notion.create_db(parent=root_page, schema=Article)
    assert db.title == ''
    assert db.description == 'My articles'
    db.delete()


def test_db_attributes(contacts_db: Database):
    assert isinstance(contacts_db.title, RichText)
    assert contacts_db.title == CONTACTS_DB

    assert isinstance(contacts_db.description, RichText)
    assert contacts_db.description == 'Database of all my contacts!'

    assert isinstance(contacts_db.icon, str)
    assert contacts_db.icon == '🤝'

    assert contacts_db.cover is None

    assert contacts_db.url.startswith('https://www.notion.so/d')

    assert not contacts_db.is_deleted

    assert not contacts_db.is_inline


def test_title_setter(notion: Session, article_db: Database):
    old_title = 'Articles'
    assert article_db.title == old_title
    new_title = 'My most favorite articles'
    article_db.title = new_title  # type: ignore
    assert article_db.title == new_title
    # clear cache and retrieve the database again to be sure it was udpated on the server side
    del notion.cache[article_db.id]
    article_db = notion.get_db(article_db.id)
    assert article_db.title == new_title
    article_db.title = RichText(old_title)
    assert article_db.title == old_title
    article_db.title = ''  # type: ignore
    assert article_db.title == ''


def test_description_setter(notion: Session, article_db: Database):
    assert article_db.description == ''

    new_description = 'My most favorite articles'
    article_db.description = new_description  # type: ignore
    assert article_db.description == new_description

    # clear cache and retrieve the database again to be sure it was udpated on the server side
    del notion.cache[article_db.id]
    article_db = notion.get_db(article_db.id)
    assert article_db.description == new_description
    article_db.description = ''  # type: ignore
    assert article_db.description == ''


def test_delete_restore_db(notion: Session, root_page: Page):
    db = notion.create_db(root_page)
    assert not db.is_deleted
    db.delete()
    assert db.is_deleted
    db.restore()
    assert not db.is_deleted


def test_reload_db(notion: Session, root_page: Page):
    db = notion.create_db(root_page)
    old_obj_id = id(db.obj_ref)
    db.reload()
    assert old_obj_id != id(db.obj_ref)


def test_new_task_db(new_task_db: Database):
    # ToDo: Implement a proper test
    pass

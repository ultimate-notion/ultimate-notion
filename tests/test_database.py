"""
Tests related to the databases.

`# type: ignore` are mostly do to mypy's too strict way of handling the type of property getters and setters.
More details here: https://github.com/python/mypy/issues/3004
"""

from __future__ import annotations

import pytest

from ultimate_notion import Database, Page, Session, Text, schema

from .conftest import CONTACTS_DB


@pytest.mark.vcr()
def test_schema(article_db: Database):
    ref_schema = article_db.schema
    assert article_db.title == 'Articles'

    assert issubclass(ref_schema, schema.Schema)
    db_schema = {
        'Name': schema.Title(),
        'Cost': schema.Number(schema.NumberFormat.DOLLAR),
        'Description': schema.Text(),
    }
    assert ref_schema.to_dict() == db_schema

    class MySchema(schema.Schema, db_title='My Schema'):
        name = schema.Property('Name', schema.Title())
        cost = schema.Property('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Property('Description', schema.Text())

    article_db.schema = MySchema

    class WrongSchema(schema.Schema, db_title='My Wrong Schema'):
        name = schema.Property('Name', schema.Title())
        cost = schema.Property('Cost', schema.Text())
        desc = schema.Property('Description', schema.Text())

    with pytest.raises(schema.SchemaError):
        article_db.schema = WrongSchema


@pytest.mark.vcr()
def test_db_without_title(notion: Session, root_page: Page):
    """Simple database of articles"""

    class Article(schema.Schema, db_title=None):
        name = schema.Property('Name', schema.Title())
        cost = schema.Property('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Property('Description', schema.Text())

    db = notion.create_db(parent=root_page, schema=Article)
    assert db.title == ''
    assert db.description == ''
    db.delete()


@pytest.mark.vcr()
def test_db_with_docstring(notion: Session, root_page: Page):
    """Simple database of articles"""

    class Article(schema.Schema, db_title=None):
        """My articles"""

        name = schema.Property('Name', schema.Title())
        cost = schema.Property('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Property('Description', schema.Text())

    db = notion.create_db(parent=root_page, schema=Article)
    assert db.title == ''
    assert db.description == 'My articles'
    db.delete()


@pytest.mark.vcr()
def test_db_attributes(contacts_db: Database):
    assert isinstance(contacts_db.title, Text)
    assert contacts_db.title == CONTACTS_DB

    assert isinstance(contacts_db.description, Text)
    assert contacts_db.description == 'Database of all my contacts!'

    assert isinstance(contacts_db.icon, str)
    assert contacts_db.icon == '🤝'

    assert contacts_db.cover is None

    assert contacts_db.url.startswith('https://www.notion.so/d')

    assert not contacts_db.is_deleted

    assert not contacts_db.is_inline


@pytest.mark.vcr()
def test_title_setter(notion: Session, article_db: Database):
    old_title = 'Articles'
    assert article_db.title == old_title
    new_title = 'My most favorite articles'
    article_db.title = new_title
    assert article_db.title == new_title
    # clear cache and retrieve the database again to be sure it was udpated on the server side
    del notion.cache[article_db.id]
    article_db = notion.get_db(article_db.id)
    assert article_db.title == new_title
    article_db.title = Text(old_title)
    assert article_db.title == old_title
    article_db.title = ''
    assert article_db.title == ''


@pytest.mark.vcr()
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


@pytest.mark.vcr()
def test_delete_restore_db(notion: Session, root_page: Page):
    db = notion.create_db(root_page)
    assert not db.is_deleted
    db.delete()
    assert db.is_deleted
    db.restore()
    assert not db.is_deleted


@pytest.mark.vcr()
def test_reload_db(notion: Session, root_page: Page):
    db = notion.create_db(root_page)
    old_obj_id = id(db.obj_ref)
    db.reload()
    assert old_obj_id != id(db.obj_ref)


@pytest.mark.vcr()
def test_parent_subdbs(notion: Session, root_page: Page):
    parent = notion.create_page(root_page, title='Parent')
    db1 = notion.create_db(parent)
    db2 = notion.create_db(parent)

    assert db1.parent == parent
    assert db2.parent == parent
    assert parent.subdbs == [db1, db2]
    assert all(isinstance(db, Database) for db in parent.subdbs)
    assert db1.ancestors == (root_page, parent)


@pytest.mark.vcr()
def test_new_task_db(new_task_db: Database):
    # ToDo: Implement a proper test
    pass

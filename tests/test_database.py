from __future__ import annotations

import pytest

from ultimate_notion import Page, RichText, Session, database, schema

from .conftest import CONTACTS_DB


def test_schema(article_db: database.Database):
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
    assert db.title is None
    db.delete()


def test_db_attributes(contacts_db):
    assert isinstance(contacts_db.title, RichText)
    assert contacts_db.title == CONTACTS_DB

    assert isinstance(contacts_db.description, RichText)
    assert contacts_db.description == 'Database of all my contacts!'

    assert isinstance(contacts_db.icon, str)
    assert contacts_db.icon == '🤝'

    assert contacts_db.cover is None

    assert contacts_db.url.startswith('https://www.notion.so/d')

    assert not contacts_db.is_archived

    assert not contacts_db.is_inline

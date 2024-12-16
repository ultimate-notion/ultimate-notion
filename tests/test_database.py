"""
Tests related to the databases.

`# type: ignore` are mostly do to mypy's too strict way of handling the type of property getters and setters.
More details here: https://github.com/python/mypy/issues/3004
"""

from __future__ import annotations

import pytest

import ultimate_notion as uno
from ultimate_notion.errors import SchemaError
from ultimate_notion.obj_api.query import MAX_PAGE_SIZE

from .conftest import CONTACTS_DB


@pytest.mark.vcr()
def test_schema(article_db: uno.Database) -> None:
    ref_schema = article_db.schema
    assert article_db.title == 'Articles'

    assert issubclass(ref_schema, uno.Schema)
    db_schema = {
        'Name': uno.PropType.Title(),
        'Cost': uno.PropType.Number(uno.NumberFormat.DOLLAR),
        'Description': uno.PropType.Text(),
    }
    assert ref_schema.to_dict() == db_schema

    class MySchema(uno.Schema, db_title='My Schema'):
        name = uno.Property('Name', uno.PropType.Title())
        cost = uno.Property('Cost', uno.PropType.Number(uno.NumberFormat.DOLLAR))
        desc = uno.Property('Description', uno.PropType.Text())

    article_db.schema = MySchema

    class WrongSchema(uno.Schema, db_title='My Wrong Schema'):
        name = uno.Property('Name', uno.PropType.Title())
        cost = uno.Property('Cost', uno.PropType.Text())
        desc = uno.Property('Description', uno.PropType.Text())

    with pytest.raises(SchemaError):
        article_db.schema = WrongSchema


@pytest.mark.vcr()
def test_db_inline(notion: uno.Session, root_page: uno.Page):
    """Simple inline database of articles"""

    class Article(uno.Schema, db_title=None):
        name = uno.Property('Name', uno.PropType.Title())
        cost = uno.Property('Cost', uno.PropType.Number(uno.NumberFormat.DOLLAR))
        desc = uno.Property('Description', uno.PropType.Text())

    db = notion.create_db(parent=root_page, schema=Article, inline=True)
    assert db.is_inline
    db.delete()


@pytest.mark.vcr()
def test_db_without_title(notion: uno.Session, root_page: uno.Page) -> None:
    """Simple database of articles"""

    class Article(uno.Schema, db_title=None):
        name = uno.Property('Name', uno.PropType.Title())
        cost = uno.Property('Cost', uno.PropType.Number(uno.NumberFormat.DOLLAR))
        desc = uno.Property('Description', uno.PropType.Text())

    db = notion.create_db(parent=root_page, schema=Article)
    assert db.title == ''
    assert db.description == ''
    db.delete()


@pytest.mark.vcr()
def test_db_with_docstring(notion: uno.Session, root_page: uno.Page) -> None:
    """Simple database of articles"""

    class Article(uno.Schema, db_title=None):
        """My articles"""

        name = uno.Property('Name', uno.PropType.Title())
        cost = uno.Property('Cost', uno.PropType.Number(uno.NumberFormat.DOLLAR))
        desc = uno.Property('Description', uno.PropType.Text())

    db = notion.create_db(parent=root_page, schema=Article)
    assert db.title == ''
    assert db.description == 'My articles'
    db.delete()


@pytest.mark.vcr()
def test_db_attributes(contacts_db: uno.Database) -> None:
    assert contacts_db.title == CONTACTS_DB
    assert contacts_db.description == 'Database of all my contacts!'
    assert isinstance(contacts_db.icon, str)
    assert contacts_db.icon == '🤝'
    assert contacts_db.cover is None
    assert contacts_db.url.startswith('https://www.notion.so/d')
    assert not contacts_db.is_deleted
    assert not contacts_db.is_inline


@pytest.mark.vcr()
def test_title_setter(notion: uno.Session, article_db: uno.Database) -> None:
    old_title = 'Articles'
    assert article_db.title == old_title
    new_title = 'My most favorite articles'
    article_db.title = new_title
    assert article_db.title == new_title
    # clear cache and retrieve the database again to be sure it was udpated on the server side
    del notion.cache[article_db.id]
    article_db = notion.get_db(article_db.id)
    assert article_db.title == new_title
    article_db.title = uno.text(old_title)
    assert article_db.title == old_title
    article_db.title = ''
    assert article_db.title == ''


@pytest.mark.vcr()
def test_description_setter(notion: uno.Session, article_db: uno.Database) -> None:
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
def test_delete_restore_db(notion: uno.Session, root_page: uno.Page) -> None:
    db = notion.create_db(root_page)
    assert not db.is_deleted
    db.delete()
    assert db.is_deleted
    db.restore()
    assert not db.is_deleted


@pytest.mark.vcr()
def test_reload_db(notion: uno.Session, root_page: uno.Page) -> None:
    db = notion.create_db(root_page)
    old_obj_id = id(db.obj_ref)
    db.reload()
    assert old_obj_id != id(db.obj_ref)


@pytest.mark.vcr()
def test_parent_subdbs(notion: uno.Session, root_page: uno.Page) -> None:
    parent = notion.create_page(root_page, title='Parent')
    db1 = notion.create_db(parent)
    db2 = notion.create_db(parent)

    assert db1.parent == parent
    assert db2.parent == parent
    assert parent.subdbs == [db1, db2]
    assert all(isinstance(db, uno.Database) for db in parent.subdbs)
    assert db1.ancestors == (root_page, parent)


@pytest.mark.vcr()
def test_more_than_max_page_size_pages(notion: uno.Session, root_page: uno.Page) -> None:
    db = notion.create_db(root_page)
    num_pages = int(1.1 * MAX_PAGE_SIZE)
    db.title = f'DB test with {num_pages} pages'
    for i in range(1, num_pages + 1):
        db.create_page(name=f'Page {i}')

    db.reload()
    assert len(db.get_all_pages()) == num_pages
    db.delete()


@pytest.mark.vcr()
def test_new_task_db(new_task_db: uno.Database) -> None:
    # ToDo: Implement a proper test
    pass

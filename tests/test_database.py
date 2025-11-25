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
        'Cost': uno.PropType.Number(format=uno.NumberFormat.DOLLAR),
        'Description': uno.PropType.Text(),
    }
    assert ref_schema.to_dict() == db_schema

    class MySchema(uno.Schema, db_title='My Schema'):
        name = uno.PropType.Title('Name')
        cost = uno.PropType.Number('Cost', format=uno.NumberFormat.DOLLAR)
        desc = uno.PropType.Text('Description')

    article_db.schema = MySchema

    class WrongSchema(uno.Schema, db_title='My Wrong Schema'):
        name = uno.PropType.Title('Name')
        cost = uno.PropType.Text('Cost')
        desc = uno.PropType.Text('Description')

    with pytest.raises(SchemaError):
        article_db.schema = WrongSchema


@pytest.mark.vcr()
def test_db_inline(notion: uno.Session, root_page: uno.Page) -> None:
    """Simple inline database of articles"""

    class Article(uno.Schema, db_title=None):
        name = uno.PropType.Title('Name')
        cost = uno.PropType.Number('Cost', format=uno.NumberFormat.DOLLAR)
        desc = uno.PropType.Text('Description')

    db = notion.create_ds(parent=root_page, schema=Article, inline=True)
    assert db.is_inline
    db.is_inline = False
    assert not db.is_inline
    db.reload()  # reload to get the updated value
    assert not db.is_inline
    db.delete()


@pytest.mark.vcr()
def test_db_without_title(notion: uno.Session, root_page: uno.Page) -> None:
    """Simple database of articles"""

    class Article(uno.Schema, db_title=None):
        name = uno.PropType.Title('Name')
        cost = uno.PropType.Number('Cost', format=uno.NumberFormat.DOLLAR)
        desc = uno.PropType.Text('Description')

    db = notion.create_ds(parent=root_page, schema=Article)
    assert db.title is None
    assert db.description is None
    db.delete()


@pytest.mark.vcr()
def test_db_with_title(notion: uno.Session, root_page: uno.Page) -> None:
    """Simple database of articles"""

    class Article(uno.Schema, db_title='My Articles'):
        name = uno.PropType.Title('Name')
        cost = uno.PropType.Number('Cost', format=uno.NumberFormat.DOLLAR)
        desc = uno.PropType.Text('Description')

    db = notion.create_ds(parent=root_page, schema=Article, title='Overwritten Title')
    assert db.title == 'Overwritten Title'
    assert db.description is None
    db.delete()

    db = notion.create_ds(parent=root_page, title='No Schema Used')
    assert db.title == 'No Schema Used'
    assert db.description is None
    db.delete()


@pytest.mark.vcr()
def test_db_with_docstring(notion: uno.Session, root_page: uno.Page) -> None:
    """Simple database of articles"""

    class Article(uno.Schema, db_title=None):
        """My articles"""

        name = uno.PropType.Title('Name')
        cost = uno.PropType.Number('Cost', format=uno.NumberFormat.DOLLAR)
        desc = uno.PropType.Text('Description')

    db = notion.create_ds(parent=root_page, schema=Article)
    assert db.title is None
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
    article_db = notion.get_ds(article_db.id)
    assert article_db.title == new_title
    article_db.title = uno.text(old_title)
    assert article_db.title == old_title
    article_db.title = None
    assert article_db.title is None


@pytest.mark.vcr()
def test_description_setter(notion: uno.Session, article_db: uno.Database) -> None:
    assert article_db.description is None

    new_description = 'My most favorite articles'
    article_db.description = new_description
    assert article_db.description == new_description

    # clear cache and retrieve the database again to be sure it was udpated on the server side
    del notion.cache[article_db.id]
    article_db = notion.get_ds(article_db.id)
    assert article_db.description == new_description
    article_db.description = None
    assert article_db.description is None


@pytest.mark.vcr()
def test_delete_restore_db(notion: uno.Session, root_page: uno.Page) -> None:
    db = notion.create_ds(root_page)
    assert not db.is_deleted
    db.delete()
    assert db.is_deleted
    db.restore()
    assert not db.is_deleted


@pytest.mark.vcr()
def test_reload_db(notion: uno.Session, root_page: uno.Page) -> None:
    db = notion.create_ds(root_page)
    old_obj_id = id(db.obj_ref)
    db.reload()
    assert old_obj_id != id(db.obj_ref)


@pytest.mark.vcr()
def test_parent_subdbs(notion: uno.Session, root_page: uno.Page) -> None:
    parent = notion.create_page(root_page, title='Parent')
    db1 = notion.create_ds(parent)
    db2 = notion.create_ds(parent)

    assert db1.parent == parent
    assert db2.parent == parent
    assert parent.subdbs == [db1, db2]
    assert all(isinstance(db, uno.Database) for db in parent.subdbs)
    assert db1.ancestors == (root_page, parent)


@pytest.mark.vcr()
def test_more_than_max_page_size_pages(notion: uno.Session, root_page: uno.Page) -> None:
    db = notion.create_ds(root_page)
    num_pages = int(1.1 * MAX_PAGE_SIZE)
    db.title = f'DB test with {num_pages} pages'
    for i in range(1, num_pages + 1):
        db.create_page(name=f'Page {i}')

    db.reload()
    assert len(db.get_all_pages()) == num_pages
    db.delete()


@pytest.mark.vcr()
def test_property_description(contacts_db: uno.Database) -> None:
    assert contacts_db.schema['Title'].description == 'Title within the company'


@pytest.mark.vcr()
def test_get_or_create_db(notion: uno.Session, root_page: uno.Page) -> None:  # issue #134
    unique_id = 42  # makes sure that dbs are not even in the trash!

    class Size(uno.OptionNS):
        """Namespace for the select options of our various sizes."""

        S = uno.Option(name='S', color=uno.Color.GREEN)
        M = uno.Option(name='M', color=uno.Color.YELLOW)
        L = uno.Option(name='L', color=uno.Color.RED)

    class Item(uno.Schema, db_title=f'Item DB {unique_id}'):
        """Database of all the items we sell."""

        name = uno.PropType.Title('Name')
        size = uno.PropType.Select('Size', options=Size)
        price = uno.PropType.Number('Price', format=uno.NumberFormat.DOLLAR)
        bought_by = uno.PropType.Relation('Bought by')

    class Customer(uno.Schema, db_title=f'Customer DB {unique_id}'):
        """Database of all our beloved customers."""

        name = uno.PropType.Title('Name')
        purchases = uno.PropType.Relation(
            'Items Purchased',
            schema=Item,
            two_way_prop=Item.bought_by,
        )

    # first call creates the dbs
    notion.get_or_create_ds(parent=root_page, schema=Item)
    notion.get_or_create_ds(parent=root_page, schema=Customer)

    # we recreate the same schema classes to make sure that we do not rely on the class identity
    class SameItem(uno.Schema, db_title=f'Item DB {unique_id}'):
        """Database of all the items we sell."""

        name = uno.PropType.Title('Name')
        size = uno.PropType.Select('Size', options=Size)
        price = uno.PropType.Number('Price', format=uno.NumberFormat.DOLLAR)
        bought_by = uno.PropType.Relation('Bought by')

    class SameCustomer(uno.Schema, db_title=f'Customer DB {unique_id}'):
        """Database of all our beloved customers."""

        name = uno.PropType.Title('Name')
        purchases = uno.PropType.Relation(
            'Items Purchased',
            schema=Item,
            two_way_prop=Item.bought_by,
        )

    # second call should retrieve the dbs
    notion.cache.clear()
    notion.get_or_create_ds(parent=root_page, schema=SameItem)
    notion.get_or_create_ds(parent=root_page, schema=SameCustomer)


@pytest.mark.vcr()
def test_new_task_db(new_task_db: uno.Database) -> None:
    # ToDo: Implement a proper test
    pass

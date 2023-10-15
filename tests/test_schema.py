from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ultimate_notion import Session, props, schema
from ultimate_notion.database import Database
from ultimate_notion.objects import File, Option
from ultimate_notion.page import Page
from ultimate_notion.schema import Column, Function, PageSchema, ReadOnlyColumnError, SchemaError


def test_all_createable_cols_schema(notion: Session, root_page: Page):
    class SchemaA(PageSchema, db_title='Schema A'):
        """Only used to create relations in Schema B"""

        name = Column('Name', schema.Title())
        relation = Column('Relation', schema.Relation())

    options = [Option(name='Option1'), Option(name='Option2', color='red')]

    class SchemaB(PageSchema, db_title='Schema B'):
        """Acutal interesting schema/db"""

        checkbox = Column('Checkbox', schema.Checkbox())
        created_by = Column('Created by', schema.CreatedBy())
        created_time = Column('Created time', schema.CreatedTime())
        date = Column('Date', schema.Date())
        email = Column('Email', schema.Email())
        files = Column('Files', schema.Files())
        formula = Column('Formula', schema.Formula('prop("Number") * 2'))
        last_edited_by = Column('Last edited by', schema.LastEditedBy())
        last_edited_time = Column('Last edited time', schema.LastEditedTime())
        multi_select = Column('Multi-select', schema.MultiSelect(options))
        number = Column('Number', schema.Number(schema.NumberFormat.DOLLAR))
        people = Column('People', schema.People())
        phone_number = Column('Phone number', schema.PhoneNumber())
        relation = Column('Relation', schema.Relation(SchemaA))
        relation_twoway = Column('Relation two-way', schema.Relation(SchemaA, two_way_prop=SchemaA.relation))
        rollup = Column('Rollup', schema.Rollup(relation, SchemaA.name, Function.COUNT))
        select = Column('Select', schema.Select(options))
        # status = Column('Status', schema.Status()) # 2023-08-11: is not yet supported by Notion API
        text = Column('Text', schema.Text())
        title = Column('Title', schema.Title())
        url = Column('URL', schema.URL())
        # unique_id = Column('Unique ID', schema.ID()) # 2023-08-11: is not yet supported by Notion API

    db_a = notion.create_db(parent=root_page, schema=SchemaA)
    db_b = notion.create_db(parent=root_page, schema=SchemaB)

    with pytest.raises(SchemaError):
        SchemaB.create(non_existent_attr_name=None)

    with pytest.raises(ReadOnlyColumnError):
        SchemaB.create(created_time=datetime.now(tz=timezone.utc))

    with pytest.raises(ReadOnlyColumnError):
        SchemaB.create(last_edited_time=datetime.now(tz=timezone.utc))

    user = next(user for user in notion.all_users() if user.is_person)
    with pytest.raises(ReadOnlyColumnError):
        SchemaB.create(created_by=user)

    with pytest.raises(ReadOnlyColumnError):
        SchemaB.create(last_edited_by=user)

    with pytest.raises(ReadOnlyColumnError):
        SchemaB.create(formula=3)

    with pytest.raises(ReadOnlyColumnError):
        SchemaB.create(rollup=3)

    a_item1 = db_a.create_page(name='Item 1')
    a_item2 = db_a.create_page(name='Item 2')

    kwargs = {
        'checkbox': props.Checkbox(True),
        'date': props.Date(datetime.now(tz=timezone.utc).date()),
        'email': props.Email('email@provider.com'),
        'files': props.Files([File('https://...')]),
        'multi_select': props.MultiSelect(options[0]),
        'number': props.Number(42),
        'people': props.People(user),
        'phone_number': props.PhoneNumber('+1 234 567 890'),
        'relation': props.Relations([a_item1, a_item2]),
        'relation_twoway': props.Relations([a_item1, a_item2]),
        'select': props.Select(options[0]),
        'text': props.Text('Text'),
        'title': props.Title('Title'),
        'url': props.URL('https://ultimate-notion.com/'),
    }

    b_item0 = SchemaB.create()  # empty page with not even a title
    writeable_props = [prop_name for prop_name, prop_type in SchemaB.to_dict().items() if not prop_type.readonly]
    for prop_name in writeable_props:
        assert not b_item0.props[prop_name].value  # False, empty list or None

    # creating a page using proper PropertyValues
    b_item1 = db_b.create_page(**kwargs)

    # creating a page using raw Python types using the Schema directly
    b_item2 = SchemaB.create(**{kwarg: prop_value.value for kwarg, prop_value in kwargs.items()})

    for item in (b_item1, b_item2):
        for kwarg, prop in kwargs.items():
            assert getattr(item.props, kwarg) == prop
            col: Column = getattr(SchemaB, kwarg)
            assert item.props[col.name] == prop

    db_a.delete()
    db_b.delete()


def test_all_cols_schema(all_cols_db: Database):
    schema_dct = all_cols_db.schema.to_dict()
    assert len(schema_dct) == 25


def test_wiki_db_schema(wiki_db: Database):
    schema_dct = wiki_db.schema.to_dict()
    assert len(schema_dct) == 5  # title, last_edited_time, owner, tags, verification
    wiki_db.pages()


def test_two_way_prop(notion: Session, root_page: Page):
    class SchemaA(PageSchema, db_title='Schema A'):
        """Only used to create relations in Schema B"""

        name = Column('Name', schema.Title())
        relation = Column('Relation', schema.Relation())

    class SchemaB(PageSchema, db_title='Schema B'):
        """Only used to create relations in Schema B"""

        relation_twoway = Column('Relation two-way', schema.Relation(SchemaA, two_way_prop=SchemaA.relation))
        title = Column('Title', schema.Title())

    db_a = notion.create_db(parent=root_page, schema=SchemaA)
    db_b = notion.create_db(parent=root_page, schema=SchemaB)

    assert db_b.schema.relation_twoway.type.two_way_prop is SchemaA.relation  # type: ignore
    assert db_a.schema.relation.type.two_way_prop is SchemaB.relation_twoway  # type: ignore

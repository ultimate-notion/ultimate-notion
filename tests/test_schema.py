from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ultimate_notion import Color, Session, props, schema
from ultimate_notion.database import Database
from ultimate_notion.objects import File, Option
from ultimate_notion.page import Page
from ultimate_notion.props import PropertyValue
from ultimate_notion.schema import AggFunc, Column, PageSchema, ReadOnlyColumnError, SchemaError


def test_all_createable_cols_schema(notion: Session, root_page: Page):
    class SchemaA(PageSchema, db_title='Schema A'):
        """Only used to create relations in Schema B"""

        name = Column('Name', schema.Title())
        relation = Column('Relation', schema.Relation())

    options = [Option(name='Option1'), Option(name='Option2', color=Color.RED)]

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
        relation_twoway = Column('Relation two-way', schema.Relation(SchemaA, two_way_col=SchemaA.relation))
        rollup = Column('Rollup', schema.Rollup(relation, SchemaA.name, AggFunc.COUNT))
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

    florian = notion.search_user('Florian Wilhelm').item()
    myself = notion.whoami()

    with pytest.raises(ReadOnlyColumnError):
        SchemaB.create(created_by=myself)

    with pytest.raises(ReadOnlyColumnError):
        SchemaB.create(last_edited_by=myself)

    with pytest.raises(ReadOnlyColumnError):
        SchemaB.create(formula=3)

    with pytest.raises(ReadOnlyColumnError):
        SchemaB.create(rollup=3)

    a_item1 = db_a.create_page(name='Item 1')
    a_item2 = db_a.create_page(name='Item 2')

    kwargs: dict[str, PropertyValue] = {
        'checkbox': props.Checkbox(True),
        'date': props.Date(datetime.now(tz=timezone.utc).date()),
        'email': props.Email('email@provider.com'),
        'files': props.Files([File(name='My File', url='https://...')]),
        'multi_select': props.MultiSelect(options[0]),
        'number': props.Number(42),
        'people': props.People(florian),
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
    wiki_db.fetch_all()


def test_two_way_col(notion: Session, root_page: Page):
    class SchemaA(PageSchema, db_title='Schema A'):
        """Only used to create relations in Schema B"""

        name = Column('Name', schema.Title())
        relation = Column('Relation', schema.Relation())

    class SchemaB(PageSchema, db_title='Schema B'):
        """Only used to create relations in Schema B"""

        relation_twoway = Column('Relation two-way', schema.Relation(SchemaA, two_way_col=SchemaA.relation))
        title = Column('Title', schema.Title())

    db_a = notion.create_db(parent=root_page, schema=SchemaA)
    db_b = notion.create_db(parent=root_page, schema=SchemaB)

    assert db_b.schema.relation_twoway.type.two_way_col is SchemaA.relation  # type: ignore
    assert db_a.schema.relation.type.two_way_col is SchemaB.relation_twoway  # type: ignore


def test_self_ref_relation(notion: Session, root_page: Page):
    class SchemaA(PageSchema, db_title='Schema A'):
        """Schema A description"""

        name = Column('Name', schema.Title())
        relation = Column('Relation', schema.Relation(schema.SelfRef))

    db_a = notion.create_db(parent=root_page, schema=SchemaA)

    assert db_a.schema.relation._schema is db_a._schema  # type: ignore


# ToDo: Reactivate after the bug on the Notion API side is fixd that adding a two-way relation column with update
#       actually generates a one-way relation column.
# def test_self_ref_two_way_col(notion: Session, root_page: Page):
#     class SchemaA(PageSchema, db_title='Schema A'):
#         """Schema A description"""

#         name = Column('Name', schema.Title())
#         fwd_rel = Column('Forward Relation', schema.Relation())
#         bwd_rel = Column('Backward Relation', schema.Relation(schema.SelfRef, two_way_col=fwd_rel))

#     db_a = notion.create_db(parent=root_page, schema=SchemaA)

#     assert db_a.schema.fwd_rel._schema is db_a._schema  # type: ignore
#     assert db_a.schema.bwd_rel._schema is db_a._schema  # type: ignore

#     assert db_a.schema.fwd_rel.type.name == 'Forward Relation'  # type: ignore
#     assert db_a.schema.bwd_rel.type.name == 'Backward Relation'  # type: ignore

#     assert db_a.schema.fwd_rel.type.two_way_col is SchemaA.bwd_rel  # type: ignore
#     assert db_a.schema.bwd_rel.type.two_way_col is SchemaA.fwd_rel  # type: ignore


def test_schema_from_dict():
    class ClassStyleSchema(PageSchema, db_title='Class Style'):
        name = Column('Name', schema.Title())
        tags = Column('Tags', schema.MultiSelect([]))

    dict_style_schema = {'Name': schema.Title(), 'Tags': schema.MultiSelect([])}
    DictStyleSchema = PageSchema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806
    assert DictStyleSchema.is_consistent_with(ClassStyleSchema)

    dict_style_schema = {'Name': schema.Title(), 'Tags': schema.Select([])}  # Wrong PropertyType here!
    DictStyleSchema = PageSchema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806
    assert not DictStyleSchema.is_consistent_with(ClassStyleSchema)

    dict_style_schema = {'Name': schema.Title(), 'My Tags': schema.MultiSelect([])}  # Wrong column name here!
    DictStyleSchema = PageSchema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806
    assert not DictStyleSchema.is_consistent_with(ClassStyleSchema)

    with pytest.raises(SchemaError):
        dict_style_schema = {'Tags': schema.MultiSelect([])}
        DictStyleSchema = PageSchema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806

    with pytest.raises(SchemaError):
        dict_style_schema = {'Name1': schema.Title(), 'Name2': schema.Title()}
        DictStyleSchema = PageSchema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806

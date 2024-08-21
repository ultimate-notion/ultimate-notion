from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ultimate_notion import Color, Session, props, schema
from ultimate_notion.database import Database
from ultimate_notion.file import FileInfo
from ultimate_notion.option import Option
from ultimate_notion.page import Page
from ultimate_notion.props import PropertyValue
from ultimate_notion.schema import AggFunc, Property, ReadOnlyPropertyError, Schema, SchemaError


@pytest.mark.vcr()
def test_all_createable_props_schema(notion: Session, root_page: Page):
    class SchemaA(Schema, db_title='Schema A'):
        """Only used to create relations in Schema B"""

        name = Property('Name', schema.Title())
        relation = Property('Relation', schema.Relation())

    options = [Option(name='Option1'), Option(name='Option2', color=Color.RED)]

    class SchemaB(Schema, db_title='Schema B'):
        """Acutal interesting schema/db"""

        checkbox = Property('Checkbox', schema.Checkbox())
        created_by = Property('Created by', schema.CreatedBy())
        created_time = Property('Created time', schema.CreatedTime())
        date = Property('Date', schema.Date())
        email = Property('Email', schema.Email())
        files = Property('Files', schema.Files())
        formula = Property('Formula', schema.Formula('prop("Number") * 2'))
        last_edited_by = Property('Last edited by', schema.LastEditedBy())
        last_edited_time = Property('Last edited time', schema.LastEditedTime())
        multi_select = Property('Multi-select', schema.MultiSelect(options))
        number = Property('Number', schema.Number(schema.NumberFormat.DOLLAR))
        people = Property('People', schema.People())
        phone_number = Property('Phone number', schema.PhoneNumber())
        relation = Property('Relation', schema.Relation(SchemaA))
        relation_twoway = Property('Relation two-way', schema.Relation(SchemaA, two_way_prop=SchemaA.relation))
        rollup = Property('Rollup', schema.Rollup(relation, SchemaA.name, AggFunc.COUNT))
        select = Property('Select', schema.Select(options))
        # status = Property('Status', schema.Status()) # 2023-08-11: is not yet supported by Notion API
        text = Property('Text', schema.Text())
        title = Property('Title', schema.Title())
        url = Property('URL', schema.URL())
        # unique_id = Property('Unique ID', schema.ID()) # 2023-08-11: is not yet supported by Notion API

    db_a = notion.create_db(parent=root_page, schema=SchemaA)
    db_b = notion.create_db(parent=root_page, schema=SchemaB)

    with pytest.raises(SchemaError):
        SchemaB.create(non_existent_attr_name=None)

    with pytest.raises(ReadOnlyPropertyError):
        SchemaB.create(created_time=datetime.now(tz=timezone.utc))

    with pytest.raises(ReadOnlyPropertyError):
        SchemaB.create(last_edited_time=datetime.now(tz=timezone.utc))

    florian = notion.search_user('Florian Wilhelm').item()
    myself = notion.whoami()

    with pytest.raises(ReadOnlyPropertyError):
        SchemaB.create(created_by=myself)

    with pytest.raises(ReadOnlyPropertyError):
        SchemaB.create(last_edited_by=myself)

    with pytest.raises(ReadOnlyPropertyError):
        SchemaB.create(formula=3)

    with pytest.raises(ReadOnlyPropertyError):
        SchemaB.create(rollup=3)

    a_item1 = db_a.create_page(name='Item 1')
    a_item2 = db_a.create_page(name='Item 2')

    kwargs: dict[str, PropertyValue] = {
        'checkbox': props.Checkbox(True),
        'date': props.Date(datetime.now(tz=timezone.utc).date()),
        'email': props.Email('email@provider.com'),
        'files': props.Files([FileInfo(name='My File', url='https://...')]),
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
        for kwarg, prop_val in kwargs.items():
            assert getattr(item.props, kwarg) == prop_val
            prop: Property = getattr(SchemaB, kwarg)
            assert item.props[prop.name] == prop_val

    db_a.delete()
    db_b.delete()


@pytest.mark.vcr()
def test_all_props_schema(all_props_db: Database):
    schema_dct = all_props_db.schema.to_dict()
    assert len(schema_dct) == 25


@pytest.mark.vcr()
def test_wiki_db_schema(wiki_db: Database):
    schema_dct = wiki_db.schema.to_dict()
    assert len(schema_dct) == 5  # title, last_edited_time, owner, tags, verification
    wiki_db.fetch_all()


@pytest.mark.vcr()
def test_two_way_prop(notion: Session, root_page: Page):
    class SchemaA(Schema, db_title='Schema A'):
        """Only used to create relations in Schema B"""

        name = Property('Name', schema.Title())
        relation = Property('Relation', schema.Relation())

    class SchemaB(Schema, db_title='Schema B'):
        """Only used to create relations in Schema B"""

        relation_twoway = Property('Relation two-way', schema.Relation(SchemaA, two_way_prop=SchemaA.relation))
        title = Property('Title', schema.Title())

    db_a = notion.create_db(parent=root_page, schema=SchemaA)
    db_b = notion.create_db(parent=root_page, schema=SchemaB)

    assert db_b.schema.relation_twoway.type.two_way_prop is SchemaA.relation  # type: ignore
    assert db_a.schema.relation.type.two_way_prop is SchemaB.relation_twoway  # type: ignore


@pytest.mark.vcr()
def test_self_ref_relation(notion: Session, root_page: Page):
    class SchemaA(Schema, db_title='Schema A'):
        """Schema A description"""

        name = Property('Name', schema.Title())
        relation = Property('Relation', schema.Relation(schema.SelfRef))

    db_a = notion.create_db(parent=root_page, schema=SchemaA)

    assert db_a.schema.relation._schema is db_a._schema  # type: ignore


# ToDo: Reactivate after the bug on the Notion API side is fixed that adding a two-way relation property with update
#       actually generates a one-way relation property.
# @pytest.mark.vcr()
# def test_self_ref_two_way_prop(notion: Session, root_page: Page):
#     class SchemaA(Schema, db_title='Schema A'):
#         """Schema A description"""

#         name = Property('Name', schema.Title())
#         fwd_rel = Property('Forward Relation', schema.Relation())
#         bwd_rel = Property('Backward Relation', schema.Relation(schema.SelfRef, two_way_prop=fwd_rel))

#     db_a = notion.create_db(parent=root_page, schema=SchemaA)

#     assert db_a.schema.fwd_rel._schema is db_a._schema  # type: ignore
#     assert db_a.schema.bwd_rel._schema is db_a._schema  # type: ignore

#     assert db_a.schema.fwd_rel.type.name == 'Forward Relation'  # type: ignore
#     assert db_a.schema.bwd_rel.type.name == 'Backward Relation'  # type: ignore

#     assert db_a.schema.fwd_rel.type.two_way_prop is SchemaA.bwd_rel  # type: ignore
#     assert db_a.schema.bwd_rel.type.two_way_prop is SchemaA.fwd_rel  # type: ignore


@pytest.mark.vcr()
def test_schema_from_dict():
    class ClassStyleSchema(Schema, db_title='Class Style'):
        name = Property('Name', schema.Title())
        tags = Property('Tags', schema.MultiSelect([]))

    dict_style_schema = {'Name': schema.Title(), 'Tags': schema.MultiSelect([])}
    DictStyleSchema = Schema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806
    assert DictStyleSchema.is_consistent_with(ClassStyleSchema)

    dict_style_schema = {'Name': schema.Title(), 'Tags': schema.Select([])}  # Wrong PropertyType here!
    DictStyleSchema = Schema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806
    assert not DictStyleSchema.is_consistent_with(ClassStyleSchema)

    dict_style_schema = {'Name': schema.Title(), 'My Tags': schema.MultiSelect([])}  # Wrong property name here!
    DictStyleSchema = Schema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806
    assert not DictStyleSchema.is_consistent_with(ClassStyleSchema)

    with pytest.raises(SchemaError):
        dict_style_schema = {'Tags': schema.MultiSelect([])}
        DictStyleSchema = Schema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806

    with pytest.raises(SchemaError):
        dict_style_schema = {'Name1': schema.Title(), 'Name2': schema.Title()}
        DictStyleSchema = Schema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806

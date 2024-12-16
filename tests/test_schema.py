from __future__ import annotations

from datetime import datetime, timezone

import pendulum as pnd
import pytest

import ultimate_notion as uno
from ultimate_notion import props
from ultimate_notion.errors import ReadOnlyPropertyError, SchemaError
from ultimate_notion.props import PropertyValue


@pytest.mark.vcr()
def test_all_createable_props_schema(notion: uno.Session, root_page: uno.Page) -> None:
    class SchemaA(uno.Schema, db_title='Schema A'):
        """Only used to create relations in Schema B"""

        name = uno.Property('Name', uno.PropType.Title())
        relation = uno.Property('Relation', uno.PropType.Relation())

    options = [uno.Option(name='Option1'), uno.Option(name='Option2', color=uno.Color.RED)]

    class SchemaB(uno.Schema, db_title='Schema B'):
        """Acutal interesting schema/db"""

        checkbox = uno.Property('Checkbox', uno.PropType.Checkbox())
        created_by = uno.Property('Created by', uno.PropType.CreatedBy())
        created_time = uno.Property('Created time', uno.PropType.CreatedTime())
        date = uno.Property('Date', uno.PropType.Date())
        email = uno.Property('Email', uno.PropType.Email())
        files = uno.Property('Files', uno.PropType.Files())
        formula = uno.Property('Formula', uno.PropType.Formula('prop("Number") * 2'))
        last_edited_by = uno.Property('Last edited by', uno.PropType.LastEditedBy())
        last_edited_time = uno.Property('Last edited time', uno.PropType.LastEditedTime())
        multi_select = uno.Property('Multi-select', uno.PropType.MultiSelect(options))
        number = uno.Property('Number', uno.PropType.Number(uno.NumberFormat.DOLLAR))
        people = uno.Property('People', uno.PropType.Person())
        phone_number = uno.Property('Phone number', uno.PropType.Phone())
        relation = uno.Property('Relation', uno.PropType.Relation(SchemaA))
        relation_twoway = uno.Property(
            'Relation two-way', uno.PropType.Relation(SchemaA, two_way_prop=SchemaA.relation)
        )
        rollup = uno.Property(
            'Rollup',
            uno.PropType.Rollup(relation_prop=relation, rollup_prop=SchemaA.name, calculate=uno.AggFunc.COUNT_ALL),
        )
        select = uno.Property('Select', uno.PropType.Select(options))
        # status = uno.Property('Status', schema.Status()) # 2023-08-11: is not yet supported by Notion API
        text = uno.Property('Text', uno.PropType.Text())
        title = uno.Property('Title', uno.PropType.Title())
        url = uno.Property('URL', uno.PropType.URL())
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
        'date': props.Date(pnd.date(2021, 1, 1)),
        'email': props.Email('email@provider.com'),
        'files': props.Files([uno.FileInfo(name='My File', url='https://...')]),
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
        assert not b_item0.props[prop_name]  # False, empty list or None

    # creating a page using proper PropertyValues
    b_item1 = db_b.create_page(**kwargs)

    # creating a page using raw Python types using the Schema directly
    b_item2 = SchemaB.create(**dict(kwargs.items()))

    for item in (b_item1, b_item2):
        for kwarg, prop_val in kwargs.items():
            assert getattr(item.props, kwarg) == prop_val.value
            prop: uno.Property = getattr(SchemaB, kwarg)
            assert item.props[prop.name] == prop_val.value

    db_a.delete()
    db_b.delete()


@pytest.mark.vcr()
def test_all_props_schema(all_props_db: uno.Database) -> None:
    schema_dct = all_props_db.schema.to_dict()
    assert len(schema_dct) == 26


@pytest.mark.vcr()
def test_wiki_db_schema(wiki_db: uno.Database) -> None:
    schema_dct = wiki_db.schema.to_dict()
    assert len(schema_dct) == 5  # title, last_edited_time, owner, tags, verification
    wiki_db.get_all_pages()


@pytest.mark.vcr()
def test_two_way_prop(notion: uno.Session, root_page: uno.Page) -> None:
    class SchemaA(uno.Schema, db_title='Schema A'):
        """Only used to create relations in Schema B"""

        name = uno.Property('Name', uno.PropType.Title())
        relation = uno.Property('Relation', uno.PropType.Relation())

    class SchemaB(uno.Schema, db_title='Schema B'):
        """Only used to create relations in Schema B"""

        relation_twoway = uno.Property(
            'Relation two-way', uno.PropType.Relation(SchemaA, two_way_prop=SchemaA.relation)
        )
        title = uno.Property('Title', uno.PropType.Title())

    db_a = notion.create_db(parent=root_page, schema=SchemaA)
    db_b = notion.create_db(parent=root_page, schema=SchemaB)

    assert db_b.schema.relation_twoway.type.two_way_prop is SchemaA.relation  # type: ignore
    assert db_a.schema.relation.type.two_way_prop is SchemaB.relation_twoway  # type: ignore


@pytest.mark.vcr()
def test_self_ref_relation(notion: uno.Session, root_page: uno.Page) -> None:
    class SchemaA(uno.Schema, db_title='Schema A'):
        """Schema A description"""

        name = uno.Property('Name', uno.PropType.Title())
        relation = uno.Property('Relation', uno.PropType.Relation(uno.SelfRef))

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
def test_schema_from_dict() -> None:
    class ClassStyleSchema(uno.Schema, db_title='Class Style'):
        name = uno.Property('Name', uno.PropType.Title())
        tags = uno.Property('Tags', uno.PropType.MultiSelect([]))

    dict_style_schema = {'Name': uno.PropType.Title(), 'Tags': uno.PropType.MultiSelect([])}
    DictStyleSchema = uno.Schema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806
    DictStyleSchema.assert_consistency_with(ClassStyleSchema)

    dict_style_schema = {'Name': uno.PropType.Title(), 'Tags': uno.PropType.Select([])}  # Wrong PropertyType!
    DictStyleSchema = uno.Schema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806

    with pytest.raises(SchemaError):
        DictStyleSchema.assert_consistency_with(ClassStyleSchema)

    dict_style_schema = {'Name': uno.PropType.Title(), 'My Tags': uno.PropType.MultiSelect([])}  # Wrong property!
    DictStyleSchema = uno.Schema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806

    with pytest.raises(SchemaError):
        DictStyleSchema.assert_consistency_with(ClassStyleSchema)

    with pytest.raises(SchemaError):
        dict_style_schema = {'Tags': uno.PropType.MultiSelect([])}
        DictStyleSchema = uno.Schema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806

    with pytest.raises(SchemaError):
        dict_style_schema = {'Name1': uno.PropType.Title(), 'Name2': uno.PropType.Title()}
        DictStyleSchema = uno.Schema.from_dict(dict_style_schema, db_title='Dict Style')  # noqa: N806

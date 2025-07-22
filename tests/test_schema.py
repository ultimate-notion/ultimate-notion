from __future__ import annotations

from datetime import datetime, timezone

import pendulum as pnd
import pytest

import ultimate_notion as uno
from ultimate_notion import props
from ultimate_notion.errors import InvalidAPIUsageError, PropertyError, ReadOnlyPropertyError, SchemaError
from ultimate_notion.props import PropertyValue
from ultimate_notion.schema import Property


@pytest.mark.vcr()
def test_all_createable_props_schema(notion: uno.Session, root_page: uno.Page) -> None:
    class SchemaA(uno.Schema, db_title='Schema A'):
        """Only used to create relations in Schema B"""

        name = uno.PropType.Title('Name')
        relation = uno.PropType.Relation('Relation')

    options = [uno.Option(name='Option1'), uno.Option(name='Option2', color=uno.Color.RED)]

    class SchemaB(uno.Schema, db_title='Schema B'):
        """Actual interesting schema/db"""

        checkbox = uno.PropType.Checkbox('Checkbox')
        created_by = uno.PropType.CreatedBy('Created by')
        created_time = uno.PropType.CreatedTime('Created time')
        date = uno.PropType.Date('Date')
        email = uno.PropType.Email('Email')
        files = uno.PropType.Files('Files')
        formula = uno.PropType.Formula('Formula', formula='prop("Number") * 2')
        last_edited_by = uno.PropType.LastEditedBy('Last edited by')
        last_edited_time = uno.PropType.LastEditedTime('Last edited time')
        multi_select = uno.PropType.MultiSelect('Multi-select', options=options)
        number = uno.PropType.Number('Number', format=uno.NumberFormat.DOLLAR)
        people = uno.PropType.Person('People')
        phone_number = uno.PropType.Phone('Phone number')
        relation = uno.PropType.Relation('Relation', schema=SchemaA)
        relation_twoway = uno.PropType.Relation('Relation two-way', schema=SchemaA, two_way_prop=SchemaA.relation)
        rollup = uno.PropType.Rollup(
            'Rollup',
            relation=relation,
            rollup=SchemaA.name,
            calculate=uno.AggFunc.COUNT_ALL,
        )
        select = uno.PropType.Select('Select', options=options)
        # status = uno.PropType.Status('Status')  # 2025-06-30: is not yet supported by Notion API
        text = uno.PropType.Text('Text')
        title = uno.PropType.Title('Title')
        url = uno.PropType.URL('URL')
        # unique_id = uno.PropType.ID('Unique ID')  # 2025-06-30: is not yet supported by Notion API

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
        'people': props.Person(florian),
        'phone_number': props.Phone('+1 234 567 890'),
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

    # creating a page using raw Python types and the Schema directly
    b_item2 = SchemaB.create(**{name: prop.value for name, prop in kwargs.items()})

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

        name = uno.PropType.Title('Name')
        relation = uno.PropType.Relation('Relation')

    class SchemaB(uno.Schema, db_title='Schema B'):
        """Only used to create relations in Schema B"""

        relation_twoway = uno.PropType.Relation('Relation two-way', schema=SchemaA, two_way_prop=SchemaA.relation)
        title = uno.PropType.Title('Title')

    db_a = notion.create_db(parent=root_page, schema=SchemaA)
    db_b = notion.create_db(parent=root_page, schema=SchemaB)

    assert db_b.schema.relation_twoway.two_way_prop is SchemaA.relation  # type: ignore
    assert db_a.schema.relation.two_way_prop is SchemaB.relation_twoway  # type: ignore


@pytest.mark.vcr()
def test_self_ref_relation(notion: uno.Session, root_page: uno.Page) -> None:
    class SchemaA(uno.Schema, db_title='Schema A'):
        """Schema A description"""

        name = uno.PropType.Title('Name')
        relation = uno.PropType.Relation('Relation', schema=uno.SelfRef)

    db_a = notion.create_db(parent=root_page, schema=SchemaA)

    assert db_a.schema.relation._schema is db_a._schema  # type: ignore


# ToDo: Reactivate after the bug on the Notion API side is fixed that adding a two-way relation property with update
#       actually generates a one-way relation property.
# @pytest.mark.vcr()
# def test_self_ref_two_way_prop(notion: uno.Session, root_page: uno.Page):
#     class SchemaA(uno.Schema, db_title='Schema A'):
#         """Schema A description"""

#         name = uno.PropType.Title('Name')
#         fwd_rel = uno.PropType.Relation('Forward Relation')
#         bwd_rel = uno.PropType.Relation('Backward Relation', schema=uno.SelfRef, two_way_prop=fwd_rel)

#     db_a = notion.create_db(parent=root_page, schema=SchemaA)

#     assert db_a.schema.fwd_rel._schema is db_a._schema  # type: ignore
#     assert db_a.schema.bwd_rel._schema is db_a._schema  # type: ignore

#     assert db_a.schema.fwd_rel.name == 'Forward Relation'  # type: ignore
#     assert db_a.schema.bwd_rel.name == 'Backward Relation'  # type: ignore

#     assert db_a.schema.fwd_rel.two_way_prop is SchemaA.bwd_rel  # type: ignore
#     assert db_a.schema.bwd_rel.two_way_prop is SchemaA.fwd_rel  # type: ignore


def test_title_missing_or_too_many() -> None:
    with pytest.raises(SchemaError):

        class MissingTitleSchema(uno.Schema, db_title='Missing Title'):
            tags = uno.PropType.MultiSelect('Tags', options=[])

    with pytest.raises(SchemaError):

        class TwoTitleSchema(uno.Schema, db_title='Two Titles'):
            title = uno.PropType.Title('Title')
            name = uno.PropType.Title('Name')


def test_unique_property_names() -> None:
    with pytest.raises(SchemaError):

        class AmbiguousPropSchema(uno.Schema, db_title='Ambiguous Properties'):
            title = uno.PropType.Title('Title')
            tags = uno.PropType.MultiSelect('Tags', options=[])
            select = uno.PropType.Select('Tags', options=[])


def test_property_name_is_set() -> None:
    with pytest.raises(PropertyError):

        class NoNameSchema(uno.Schema, db_title='No Name Set'):
            title = uno.PropType.Title('Title')
            tags = uno.PropType.Number()


def test_to_pydantic_model() -> None:
    class Schema(uno.Schema, db_title='Schema'):
        name = uno.PropType.Title('Name')
        tags = uno.PropType.MultiSelect('Tags', options=[])
        created_on = uno.PropType.CreatedTime('Created on')

    rw_props_model = Schema.to_pydantic_model(with_ro_props=False)
    rw_props_item = rw_props_model(**{'Name': 'Name', 'Tags': ['Tag1', 'Tag2']})
    assert len(rw_props_item.__class__.model_fields) == 2
    assert isinstance(rw_props_item.name, PropertyValue)  # type: ignore[attr-defined]

    all_props_model = Schema.to_pydantic_model(with_ro_props=True)
    created_on = props.CreatedTime(pnd.parse('2021-01-01T12:00:00Z'))
    all_props_item = all_props_model(**{'Name': 'Name', 'Tags': ['Tag1', 'Tag2'], 'Created on': created_on})
    assert len(all_props_item.__class__.model_fields) == 3


@pytest.mark.vcr()
def test_add_del_update_prop(notion: uno.Session, root_page: uno.Page) -> None:
    options = [uno.Option(name='Cat1', color=uno.Color.DEFAULT), uno.Option(name='Cat2', color=uno.Color.RED)]

    class Schema(uno.Schema, db_title='Add/Del/Update Prop-Test'):
        """Schema for testing adding, deleting and updating properties"""

        name = uno.PropType.Title('Name')
        cat = uno.PropType.Select('Category', options=options)
        tags = uno.PropType.MultiSelect('Tags', options=options)
        formula = uno.PropType.Formula('Formula', formula='prop("Name")')

    db = notion.create_db(parent=root_page, schema=Schema)

    # Delete properties from the schema
    assert hasattr(db.schema, 'formula')
    del db.schema['Formula']
    assert 'Formula' not in [prop.name for prop in db.schema]
    assert not hasattr(db.schema, 'formula')
    db.reload()
    assert 'Formula' not in [prop.name for prop in db.schema]
    assert not hasattr(db.schema, 'formula')

    db.schema.tags.delete()  # type: ignore[attr-defined]
    assert 'Tags' not in [prop.name for prop in db.schema]
    assert not hasattr(db.schema, 'tags')
    db.reload()
    assert 'Tags' not in [prop.name for prop in db.schema]
    assert not hasattr(db.schema, 'tags')

    # Add properties to the schema
    db.schema['Number'] = uno.PropType.Number(format=uno.NumberFormat.DOLLAR)
    assert 'Number' in [prop.name for prop in db.schema]
    assert hasattr(db.schema, 'number')
    db.reload()
    assert 'Number' in [prop.name for prop in db.schema]
    assert hasattr(db.schema, 'number')

    db.schema.date = uno.PropType.Date('Date')
    assert 'Date' in [prop.name for prop in db.schema]
    assert hasattr(db.schema, 'date')
    db.reload()
    assert 'Date' in [prop.name for prop in db.schema]
    assert hasattr(db.schema, 'date')

    # Update properties in the schema
    with pytest.raises(PropertyError):
        db.schema['Number'] = uno.PropType.Formula('New Name', formula='prop("Name") + "!"')

    db.schema['Number'] = uno.PropType.Formula(formula='prop("Name") + "!"')
    assert db.schema['Number'].formula.startswith('{{notion:block_property:title:')  # type: ignore[attr-defined]
    db.reload()
    assert db.schema['Number'].formula.startswith('{{notion:block_property:title:')  # type: ignore[attr-defined]

    db.schema.number = uno.PropType.Number(format=uno.NumberFormat.PERCENT)
    assert db.schema.number.format == uno.NumberFormat.PERCENT
    db.reload()
    assert db.schema.number.format == uno.NumberFormat.PERCENT


@pytest.mark.vcr()
def test_update_prop_type_attrs(notion: uno.Session, root_page: uno.Page) -> None:
    class SchemaA(uno.Schema, db_title='Update Prop-Test: Schema A'):
        """Only used to create relations in Schema C"""

        name = uno.PropType.Title('Name')
        relation = uno.PropType.Relation('Relation')

    class SchemaB(uno.Schema, db_title='Update Prop-Test: Schema B'):
        """Only used to create relations in Schema C"""

        name = uno.PropType.Title('Name')
        relation = uno.PropType.Relation('Relation')

    class SchemaC(uno.Schema, db_title='Update Prop-Test: Schema C'):
        """Actual interesting schema/db"""

        name = uno.PropType.Title('Name')
        relation = uno.PropType.Relation('Relation', schema=SchemaA)
        relation_twoway = uno.PropType.Relation('Relation two-way', schema=SchemaA, two_way_prop=SchemaA.relation)
        rollup = uno.PropType.Rollup(
            'Rollup',
            relation=relation,
            rollup=SchemaA.name,
            calculate=uno.AggFunc.COUNT_ALL,
        )

    db_a = notion.create_db(parent=root_page, schema=SchemaA)
    db_b = notion.create_db(parent=root_page, schema=SchemaB)
    db_c = notion.create_db(parent=root_page, schema=SchemaC)

    # Set a two-way relation property
    assert db_c.schema['Relation'].two_way_prop is None  # type: ignore[attr-defined]
    two_way_prop = 'Back Relation'
    db_c.schema['Relation'].two_way_prop = two_way_prop  # type: ignore[attr-defined]
    assert db_a.schema[two_way_prop].two_way_prop.name == 'Relation'  # type: ignore[attr-defined]
    db_c.reload()
    assert db_a.schema[two_way_prop].two_way_prop.name == 'Relation'  # type: ignore[attr-defined]

    # Try renaming the two-way relation property
    two_way_prop = 'Other Back Relation'
    db_c.schema['Relation'].two_way_prop = two_way_prop  # type: ignore[attr-defined]
    assert db_a.schema[two_way_prop].two_way_prop.name == 'Relation'  # type: ignore[attr-defined]
    db_c.reload()
    assert db_a.schema[two_way_prop].two_way_prop.name == 'Relation'  # type: ignore[attr-defined]

    # Delete the two-way relation property
    db_c.schema['Relation'].two_way_prop = None  # type: ignore[attr-defined]
    assert two_way_prop not in [prop.name for prop in db_a.schema]
    db_a.reload()
    assert two_way_prop not in [prop.name for prop in db_a.schema]

    # Change target from SchemaA to SchemaB for one-way and two-way relations
    for rel in ('Relation', 'Relation two-way'):
        assert db_c.schema[rel].schema == db_a.schema  # type: ignore[attr-defined]
        db_c.schema[rel].schema = db_b.schema  # type: ignore[attr-defined]
        assert db_c.schema[rel].schema == db_b.schema  # type: ignore[attr-defined]
        db_c.reload()
        assert db_c.schema[rel].schema == db_b.schema  # type: ignore[attr-defined]

    # change the options of the (multi-)select property
    options = [uno.Option(name='Cat1', color=uno.Color.DEFAULT), uno.Option(name='Cat2', color=uno.Color.RED)]

    def block_ref(prop: Property) -> str:
        """Helper function to create a block reference for the formula.

        Note that Notion converts 'prop("Name")' to Jinja2-like expressions
        """
        return f'{{{{notion:block_property:{prop.id}:'

    class Schema(uno.Schema, db_title='Select Options Update Test'):
        name = uno.PropType.Title('Name')
        cat = uno.PropType.Select('Category', options=options)
        tags = uno.PropType.MultiSelect('Tags', options=options)
        formula = uno.PropType.Formula('Formula', formula='prop("Name")')
        number = uno.PropType.Number('Number', format=uno.NumberFormat.DOLLAR)

    db = notion.create_db(parent=root_page, schema=Schema)

    # Change the number format of the number property
    assert db.schema['Number'].format == uno.NumberFormat.DOLLAR  # type: ignore[attr-defined]
    db.schema['Number'].format = uno.NumberFormat.PERCENT  # type: ignore[attr-defined]
    assert db.schema['Number'].format == uno.NumberFormat.PERCENT  # type: ignore[attr-defined]
    db.reload()
    assert db.schema['Number'].format == uno.NumberFormat.PERCENT  # type: ignore[attr-defined]
    db.schema['Number'].format = uno.NumberFormat.EURO.value  # type: ignore[attr-defined]
    assert db.schema['Number'].format == uno.NumberFormat.EURO  # type: ignore[attr-defined]

    # Change the formula property
    assert db.schema['Formula'].formula.startswith(block_ref(db.schema['Name']))  # type: ignore[attr-defined]
    db.schema['Formula'].formula = 'prop("Category")'  # type: ignore[attr-defined]
    assert db.schema['Formula'].formula == 'prop("Category")'  # type: ignore[attr-defined]
    db.reload()
    assert db.schema['Formula'].formula.startswith(block_ref(db.schema['Category']))  # type: ignore[attr-defined]

    # Change the select options of the select and multi-select properties
    for prop in ('Category', 'Tags'):
        curr_cats = db.schema[prop].options  # type: ignore[attr-defined]
        assert [cat.name for cat in curr_cats] == ['Cat1', 'Cat2']

        new_cat = uno.Option(name='Cat3', color=uno.Color.RED)
        # Adding a new category to the select options
        db.schema[prop].options = [*curr_cats, new_cat]  # type: ignore[attr-defined]

        assert db.schema[prop].options == [*curr_cats, new_cat]  # type: ignore[attr-defined]
        db.reload()
        assert db.schema[prop].options == [*curr_cats, new_cat]  # type: ignore[attr-defined]

        # Removing a category from the select options
        db.schema[prop].options = [new_cat]  # type: ignore[attr-defined]
        assert db.schema[prop].options == [new_cat]  # type: ignore[attr-defined]
        db.reload()
        assert db.schema[prop].options == [new_cat]  # type: ignore[attr-defined]

        # Updating a category in the select options
        with pytest.raises(InvalidAPIUsageError):
            exist_option = uno.Option(name='Cat3', color=uno.Color.GREEN)
            # trying to update the color of an existing option
            db.schema[prop].options = [exist_option]  # type: ignore[attr-defined]

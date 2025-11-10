from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

import pendulum as pnd
import pytest

import ultimate_notion as uno
from tests.conftest import URL
from ultimate_notion import props
from ultimate_notion.errors import InvalidAPIUsageError, PropertyError, ReadOnlyPropertyError, SchemaError
from ultimate_notion.props import PropertyValue
from ultimate_notion.schema import Property


@pytest.mark.vcr()
def test_all_createable_props_schema(
    notion: uno.Session, root_page: uno.Page, dummy_urls: URL, get_id_prefix: Callable[[str], str]
) -> None:
    class SchemaA(uno.Schema, db_title='Schema A'):
        """Only used to create relations in Schema B"""

        name = uno.PropType.Title('Name')
        relation = uno.PropType.Relation('Relation')

    options = [uno.Option(name='Option1'), uno.Option(name='Option2', color=uno.Color.RED)]

    id_prefix = get_id_prefix('ALLCOLS')  # must be unique in the workspace, also considering pages in the bin

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
        unique_id = uno.PropType.ID('ID', prefix=id_prefix)

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
        'files': props.Files([uno.ExternalFile(name='My File', url=dummy_urls.file)]),
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
    assert b_item1.props.unique_id.startswith(id_prefix.upper())

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
    assert len(schema_dct) == 27


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

    assert db_a.schema.relation.schema is db_a.schema  # type: ignore


# ToDo: Reactivate after the bug on the Notion API side is fixed that adding a two-way relation property
#       on a self-reference schema leads to a Notion Internal Server Error 500.
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

    db.schema.tags.delete()
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

    class TargetSchema(uno.Schema, db_title='Add/Del/Update Prop-Test'):
        """Target schema as self-reference relations lead to a Notion Internal Server Error 500"""

        name = uno.PropType.Title('Name')

    target_db = notion.create_db(parent=root_page, schema=TargetSchema)

    db.schema['Relation'] = uno.PropType.Relation(schema=TargetSchema, two_way_prop='Back Relation')
    assert 'Relation' in [prop.name for prop in db.schema]
    assert 'Back Relation' in [prop.name for prop in target_db.schema]
    assert hasattr(db.schema, 'relation')
    assert hasattr(target_db.schema, 'back_relation')
    db.reload()
    assert 'Relation' in [prop.name for prop in db.schema]
    assert 'Back Relation' in [prop.name for prop in target_db.schema]
    assert hasattr(db.schema, 'relation')
    assert hasattr(target_db.schema, 'back_relation')

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
    db_c.reload(rebind_schema=False)  # since we changed something above
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


@pytest.mark.vcr()
def test_bind_db(notion: uno.Session, root_page: uno.Page) -> None:
    options = [uno.Option(name='Cat1', color=uno.Color.DEFAULT), uno.Option(name='Cat2', color=uno.Color.RED)]

    class OrigSchema(uno.Schema, db_title='Bind DB Test'):
        name = uno.PropType.Title('Name')
        cat = uno.PropType.Select('Category', options=options)
        tags = uno.PropType.MultiSelect('Tags', options=options)

    db = notion.create_db(parent=root_page, schema=OrigSchema)

    # Check the schema properties
    assert isinstance(db.schema.name, uno.PropType.Title)
    assert db.schema.cat.options == options  # type: ignore[attr-defined]
    assert db.schema.tags.options == options  # type: ignore[attr-defined]

    class ConsistentSchema(uno.Schema):
        my_name = uno.PropType.Title('Name')
        my_cat = uno.PropType.Select('Category', options=options)
        my_tags = uno.PropType.MultiSelect('Tags', options=options)

    ConsistentSchema.bind_db(db)

    # Check the schema attribute names
    assert isinstance(db.schema.my_name, uno.PropType.Title)
    assert db.schema.my_cat.options == options  # type: ignore[attr-defined]
    assert db.schema.my_tags.options == options  # type: ignore[attr-defined]
    assert not hasattr(db.schema, 'name')
    assert not hasattr(db.schema, 'cat')
    assert not hasattr(db.schema, 'tags')


@pytest.mark.vcr()
def test_bind_db_auto(notion: uno.Session) -> None:
    class StatusOption(uno.OptionNS):
        backlog = uno.Option('Backlog', color=uno.Color.GRAY)
        in_progress = uno.Option('In Progress', color=uno.Color.BLUE)
        blocked = uno.Option('Blocked', color=uno.Color.RED)
        done = uno.Option('Done', color=uno.Color.GREEN)

    priority_options = [
        uno.Option('✹ High', color=uno.Color.RED),
        uno.Option('✷ Medium', color=uno.Color.YELLOW),
        uno.Option('✶ Low', color=uno.Color.GRAY),
    ]
    formula = (
        'if(prop("Status") == "Done", "✅", '
        'if(empty(prop("Due Date")), "", '
        'if(formatDate(now(), "YWD") == formatDate(prop("Due Date"), "YWD"), "🔹 Today", '
        'if(now() > prop("Due Date"), '
        '"🔥 " + compactDays(), '
        '"🕐 " + compactDays()'
        '))))'
    )
    compact_days_formula = (
        '('
        'if(if(empty(prop("Due Date")), toNumber(""), dateBetween(prop("Due Date"), now(), "days")) < 0, "-", "") + '
        'if((if(if(empty(prop("Due Date")), toNumber(""), '
        'dateBetween(prop("Due Date"), now(), "days")) < 0, -1, 1) * '
        'floor(abs(if(empty(prop("Due Date")), toNumber(""), '
        'dateBetween(prop("Due Date"), now(), "days")) / 7))) == 0, '
        '"", format(abs(if(if(empty(prop("Due Date")), toNumber(""), '
        'dateBetween(prop("Due Date"), now(), "days")) < 0, '
        '-1, 1) * floor(abs(if(empty(prop("Due Date")), toNumber(""), '
        'dateBetween(prop("Due Date"), now(), "days")) / 7)))) '
        '+ "w")'
        ') + '
        'if((if(empty(prop("Due Date")), toNumber(""), dateBetween(prop("Due Date"), now(), "days")) % 7) == 0, "", '
        'format(abs(if(empty(prop("Due Date")), toNumber(""), '
        'dateBetween(prop("Due Date"), now(), "days"))) % 7) + "d"'
        ')'
    )
    formula = formula.replace('compactDays()', compact_days_formula)

    class TaskBase(uno.Schema):
        task = uno.PropType.Title('Task')
        due_date = uno.PropType.Date('Due Date')
        priority = uno.PropType.Select('Priority', options=priority_options)
        status = uno.PropType.Status(
            'Status',
            to_do=[StatusOption.backlog, StatusOption.blocked],
            in_progress=[StatusOption.in_progress],
            complete=[StatusOption.done],
        )
        urgency = uno.PropType.Formula('Urgency', formula=formula)

    with pytest.raises(InvalidAPIUsageError):
        TaskBase.bind_db()
    assert not TaskBase.is_bound()

    class TaskWithDbId(TaskBase, db_id='b0cb6b70e740496d9c818a298fa2d5e1'):
        """Schema with a reference to a database by ID"""

    TaskWithDbId.bind_db()
    assert TaskWithDbId.is_bound()
    assert not TaskBase.is_bound()

    class TaskWithDbTitle(TaskBase, db_title='Task DB'):
        """Schema with a reference to a database by title"""

    TaskWithDbTitle.bind_db()
    assert TaskWithDbTitle.is_bound()


@pytest.mark.vcr()
def test_update_unique_id_prop(notion: uno.Session, root_page: uno.Page, get_id_prefix: Callable[[str], str]) -> None:
    old_id_prefix = get_id_prefix('OLDID')
    new_id_prefix = get_id_prefix('NEWID')

    class Schema(uno.Schema, db_title='Unique ID Update Test'):
        name = uno.PropType.Title('Name')
        unique_id = uno.PropType.ID('ID', prefix=old_id_prefix)

    db = notion.create_db(parent=root_page, schema=Schema)

    db.schema.unique_id.prefix = new_id_prefix  # type: ignore[attr-defined]
    db.reload()
    assert db.schema.unique_id.prefix.startswith(new_id_prefix)  # type: ignore[attr-defined]

    with pytest.raises(ValueError):
        db.schema.unique_id.prefix = 'Invalid Prefix!'  # type: ignore[attr-defined]

    db.schema.unique_id.prefix = None  # type: ignore[attr-defined]
    assert db.schema.unique_id.prefix == ''  # type: ignore[attr-defined]

    db.schema.unique_id.prefix = ''  # type: ignore[attr-defined]
    assert db.schema.unique_id.prefix == ''  # type: ignore[attr-defined]

    class NoIDPrefixSchema(uno.Schema, db_title='No Prefix ID Test'):
        name = uno.PropType.Title('Name')
        unique_id = uno.PropType.ID('ID')

    db = notion.create_db(parent=root_page, schema=NoIDPrefixSchema)
    assert db.schema.unique_id.prefix == ''  # type: ignore[attr-defined]

    with pytest.raises(SchemaError):

        class OtherSchema(uno.Schema, db_title='Unique ID Update Test'):
            name = uno.PropType.Title('Name')
            unique_id = uno.PropType.ID('ID', prefix=old_id_prefix)
            other_id = uno.PropType.ID('Other ID')


@pytest.mark.vcr()
def test_place_property(notion: uno.Session, root_page: uno.Page) -> None:
    """Test the Place property value and property classes."""

    class Location(uno.Schema, db_title='Place Property Test'):
        name = uno.PropType.Title('Name')
        location = uno.PropType.Place('Location')

    notion.create_db(parent=root_page, schema=Location)

    my_place = Location.create(
        name='My Place',
        location=uno.PlaceDict(
            lat=52.5200,
            lon=13.4050,
            aws_place_id='ChIJAVkDPzdOqEcRcDteW0YgIQQ',
            google_place_id='ChIJAVkDPzdOqEcRcDteW0',
            address='Berlin, Germany',
        ),
    )
    val = my_place.props.location
    assert val.lat == 52.5200
    assert val.lon == 13.4050
    assert val.aws_place_id == 'ChIJAVkDPzdOqEcRcDteW0YgIQQ'
    assert val.google_place_id == 'ChIJAVkDPzdOqEcRcDteW0'
    assert val.address == 'Berlin, Germany'

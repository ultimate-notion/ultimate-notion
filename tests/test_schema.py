from ultimate_notion import schema
from ultimate_notion.schema import PageSchema, Property, Function
from ultimate_notion import Session
from ultimate_notion.page import Page
from ultimate_notion.database import Database


def test_all_creatable_cols_schema(notion: Session, root_page: Page):
    class SchemaA(PageSchema, db_title="Schema A"):
        """Only used to create relations in Schema B"""

        name = Property('Name', schema.Title())
        relation = Property('Relation', schema.Relation())

    options = [schema.SelectOption(name="Option1"), schema.SelectOption(name="Option2", color="red")]

    class SchemaB(PageSchema, db_title="Schema B"):
        """Only used to create relations in Schema B"""

        checkbox = Property('Checkbox', schema.Checkbox())
        created_by = Property('Created by', schema.CreatedBy())
        created_time = Property('Created time', schema.CreatedBy())
        date = Property('Date', schema.Date())
        email = Property('Email', schema.Email())
        files = Property('Files', schema.Files())
        formula = Property('Formula', schema.Formula('prop("Number") * 2'))
        last_edited_by = Property('Last edited by', schema.LastEditedBy())
        last_edited_time = Property('Last edited time', schema.LastEditedTime())
        multi_select = Property("Multi-select", schema.MultiSelect())
        number = Property('Number', schema.Number(schema.NumberFormat.DOLLAR))
        people = Property('People', schema.People())
        phone_number = Property('Phone number', schema.PhoneNumber())
        relation = Property('Relation', schema.Relation(SchemaA))
        relation_toway = Property('Relation two-way', schema.Relation(SchemaA, two_way_prop=SchemaA.relation))
        rollup = Property('Rollup', schema.Rollup(relation, SchemaA.name, Function.COUNT))
        select = Property('Select', schema.Select(options))
        # status = Property('Status', schema.Status()) # 2023-08-11: is not yet supported by Notion API
        text = Property('Text', schema.Text())
        title = Property('Title', schema.Title())
        url = Property('URL', schema.URL())
        # unique_id = Property('Unique ID', schema.ID()) # 2023-08-11: is not yet supported by Notion API

    db_a = notion.create_db(parent=root_page, schema=SchemaA)
    db_b = notion.create_db(parent=root_page, schema=SchemaB)


def test_all_cols_schema(all_cols_db: Database):
    schema_dct = all_cols_db.schema.to_dict()
    assert len(schema_dct) == 25


def test_wiki_db_schema(wiki_db: Database):
    schema_dct = wiki_db.schema.to_dict()
    assert len(schema_dct) == 5  # title, last_edited_time, owner, tags, verification

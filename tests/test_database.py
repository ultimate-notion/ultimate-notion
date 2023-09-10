import pytest

from ultimate_notion import database, schema


def test_schema(simple_db: database.Database):
    ref_schema = simple_db.schema

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

    simple_db.schema = MySchema

    class WrongSchema(schema.PageSchema, db_title='My Wrong Schema'):
        name = schema.Column('Name', schema.Title())
        cost = schema.Column('Cost', schema.Text())
        desc = schema.Column('Description', schema.Text())

    with pytest.raises(schema.SchemaError):
        simple_db.schema = WrongSchema

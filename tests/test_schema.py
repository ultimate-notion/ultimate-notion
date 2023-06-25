import time

from ultimate_notion import schema

# ToDo: See that these unit tests do something useful!


def test_basic_schema_dict(notion, parent_page):
    db_schema = {
        'Name': schema.Title(),
        'Cost': schema.Number(schema.NumberFormat.DOLLAR),
        'Description': schema.Text(),
    }
    db = notion.create_db(parent_page=parent_page, schema=db_schema)
    time.sleep(5)  # ToDo: add here a wait_for(id)
    notion.delete_db(db)


def test_basic_schema_class(notion, parent_page):
    class Article(schema.PageSchema):
        name = schema.Property('Name', schema.Title())
        cost = schema.Property('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Property('Description', schema.Text())

    db = notion.create_db(parent_page=parent_page, schema=Article.to_dict())
    time.sleep(5)

    notion.delete_db(db)

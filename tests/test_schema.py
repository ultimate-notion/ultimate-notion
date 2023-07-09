from ultimate_notion import schema

# ToDo: Make sure these unit tests do something useful!


def test_schema_class(notion, root_page):
    class Article(schema.PageSchema):
        name = schema.Property('Name', schema.Title())
        cost = schema.Property('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Property('Description', schema.Text())

    db = notion.create_db(parent=root_page, schema=Article)
    notion.delete_db(db)
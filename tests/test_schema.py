from ultimate_notion import schema
from ultimate_notion import Session
from ultimate_notion.page import Page

# ToDo: Make sure these unit tests do something useful!


def test_schema_class(notion: Session, root_page: Page):
    class Article(schema.PageSchema, db_title="Articles"):
        name = schema.Property('Name', schema.Title())
        cost = schema.Property('Cost', schema.Number(schema.NumberFormat.DOLLAR))
        desc = schema.Property('Description', schema.Text())

    db = notion.create_db(parent=root_page, schema=Article)
    db.delete()

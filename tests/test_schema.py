import time

from ultimate_notion import schema


def test_basic_schema(notion, parent_page):
    # ToDo: Continue work here
    # status = [
    #     schema.SelectOption(name="Backlog"),
    #     schema.SelectOption(name="Blocked", color="red"),
    #     schema.SelectOption(name="In Progress", color="yellow"),
    #     schema.SelectOption(name="Completed", color="green"),
    # ]
    #
    # # define our schema from Property Objects

    db_schema = {
        "Name": schema.Title(),
        "Estimate": schema.Number(schema.NumberFormat.DOLLAR),
        "Comment": schema.Text()
        # "Approved": schema.Checkbox(),
        # "Points": schema.Number(),
        # "Due Date": schema.Date(),
        # "Status": schema.Select[status],
        # "Last Update": schema.LastEditedTime(),
    }
    db = notion.create_db(parent_page=parent_page, schema=db_schema)
    time.sleep(5)
    notion.delete_db(db)

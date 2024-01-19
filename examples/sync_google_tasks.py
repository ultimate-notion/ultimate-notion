"""Example showing how to synchronize your tasks between Google Tasks and a Notion database.

Note: Follow this quickstart guide first to enable the Google API and create the necessary credentials:
https://developers.google.com/tasks/quickstart/python
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ultimate_notion.adapters.google import GTasksClient, SyncGTasks
from ultimate_notion import (
    OptionNS,
    Option,
    Color,
    PageSchema,
    Column,
    ColType,
    Session,
)
from ultimate_notion.adapters import sync


######################################################
# Define a real simple Notion database for our tasks #
######################################################

PARENT_PAGE = "Tests"  # Defines the page where the database should be created
today = datetime.now(tz=ZoneInfo("Europe/Berlin"))


class Status(OptionNS):
    backlog = Option("Backlog", color=Color.GRAY)
    in_progress = Option("In Progress", color=Color.BLUE)
    blocked = Option("Blocked", color=Color.RED)
    done = Option("Done", color=Color.GREEN)


class Task(PageSchema, db_title="My synched task db"):
    """My personal task list of all the important stuff I have to do"""

    task = Column("Task", ColType.Title())
    status = Column("Status", ColType.Select(Status))
    due_date = Column("Due Date", ColType.Date())


with Session() as notion:
    parent = notion.search_page(PARENT_PAGE).item()
    task_db = notion.get_or_create_db(parent=parent, schema=Task)

    if task_db.is_empty:
        Task.create(
            task="Clean the house",
            due_date=today + timedelta(days=5),
            status=Status.in_progress,
        )

        Task.create(
            task="Try out Ultimate Notion",
            due_date=today - timedelta(days=1),
            status=Status.done,
        )

        Task.create(
            task="On Notion Only",
            due_date=today + timedelta(days=3),
            status=Status.done,
        )

################################################
# Define a few Google Tasks task in a tasklist #
################################################

with GTasksClient() as gtasks:
    tasklist = gtasks.get_or_create_tasklist("My synched task list")
    if tasklist.is_empty:
        tasklist.create_task("Clean the house", due=today + timedelta(days=5))
        tasklist.create_task(
            "Try out Ultimate Notion", due=today - timedelta(days=1)
        )
        tasklist.create_task(
            "On Google Tasks only", due=today + timedelta(days=1)
        )

######################################################
# Create the Sync Task between Notion & Google Tasks #
######################################################

with Session() as notion, GTasksClient(read_only=False) as gtasks:
    task_db = notion.get_or_create_db(parent=parent, schema=Task)
    tasklist = gtasks.get_or_create_tasklist("My synched task list")

    sync_task = SyncGTasks(
        notion_db=task_db,
        tasklist=tasklist,
        completed_col=Task.status,
        completed_val=Status.done,
        not_completed_val=Status.backlog,
        due_col=Task.due_date,
    )
    # Schedule the sync task to run every 5 minutes
    sync_task.run_every(seconds=5).in_total(times=3).schedule()

    # Run all scheduled tasks
    sync.run_all_tasks()

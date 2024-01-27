"""How to synchronize your tasks between Google Tasks and a Notion database.

Note: Follow this quickstart guide first to enable the Google API and create
the necessary credentials:
https://developers.google.com/tasks/quickstart/python
"""
# mypy: disable-error-code="attr-defined"

from datetime import datetime, timedelta, timezone

from ultimate_notion import (
    Color,
    ColType,
    Column,
    Option,
    OptionNS,
    PageSchema,
    Session,
)
from ultimate_notion.adapters import sync
from ultimate_notion.adapters.google import GTasksClient, SyncGTasks

######################################################
# Define a real simple Notion database for our tasks #
######################################################

PARENT_PAGE = 'Tests'  # Defines the page where the database should be created
today = datetime(2024, 1, 1, tzinfo=timezone.utc)


class Status(OptionNS):
    backlog = Option('Backlog', color=Color.GRAY)
    in_progress = Option('In Progress', color=Color.BLUE)
    blocked = Option('Blocked', color=Color.RED)
    done = Option('Done', color=Color.GREEN)


class Task(PageSchema, db_title='My synched task db'):
    """My personal task list of all the important stuff I have to do"""

    task = Column('Task', ColType.Title())
    status = Column('Status', ColType.Select(Status))
    due_date = Column('Due Date', ColType.Date())


with Session() as notion:
    parent = notion.search_page(PARENT_PAGE).item()
    task_db = notion.get_or_create_db(parent=parent, schema=Task)

    if task_db.is_empty:
        Task.create(
            task='Clean the house',
            due_date=today + timedelta(days=5),
            status=Status.in_progress,
        )

        Task.create(
            task='Try out Ultimate Notion',
            due_date=today - timedelta(days=1),
            status=Status.done,
        )

        Task.create(
            task='On Notion Only',
            due_date=today + timedelta(days=3),
            status=Status.done,
        )

################################################
# Define a few Google Tasks task in a tasklist #
################################################

with GTasksClient() as gtasks:
    tasklist = gtasks.get_or_create_tasklist('My synched task list')
    if tasklist.is_empty:
        tasklist.create_task('Clean the house', due=today + timedelta(days=5))
        tasklist.create_task(
            'Try out Ultimate Notion', due=today - timedelta(days=1)
        )
        tasklist.create_task(
            'On Google Tasks only', due=today + timedelta(days=1)
        )

######################################################
# Create the Sync Task between Notion & Google Tasks #
######################################################

# Version 1: Using the Notion database declaration from above
with Session() as notion, GTasksClient(read_only=False) as gtasks:
    task_db = notion.get_or_create_db(parent=parent, schema=Task)
    tasklist = gtasks.get_or_create_tasklist('My synched task list')

    sync_task = SyncGTasks(
        notion_db=task_db,
        tasklist=tasklist,
        completed_col=Task.status,
        completed_val=Status.done,
        not_completed_val=Status.backlog,
        due_col=Task.due_date,
    )
    # Schedule the sync task to run every 5 minutes
    # Omit the `in_total` argument to run the task forever
    sync_task.run_every(seconds=2).in_total(times=3).schedule()

    # Run all scheduled tasks
    sync.run_all_tasks()


# Version 2: Using an existing Notion database that was created manually
with Session() as notion, GTasksClient(read_only=False) as gtasks:
    task_db = notion.search_db('My synched task db').item()
    status_col = task_db.schema.get_col('Status')
    due_date_col = task_db.schema.get_col('Due Date')
    tasklist = gtasks.get_or_create_tasklist('My synched task list')

    sync_task = SyncGTasks(
        notion_db=task_db,
        tasklist=tasklist,
        completed_col=status_col,
        completed_val=status_col.type.options['Done'],
        not_completed_val=status_col.type.options['Backlog'],
        due_col=due_date_col,
    )
    sync_task.run_every(seconds=2).in_total(times=3).schedule()
    sync.run_all_tasks()

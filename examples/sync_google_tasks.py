"""How to synchronize your tasks between Google Tasks and a Notion database.

There are two ways to do this:
1. using a declarative Notion database definition or
2. using an existing Notion database that was created manually.

Note: Follow this guide first to enable the Google API and create the
necessary credentials: https://developers.google.com/tasks/quickstart/python
"""
# mypy: disable-error-code="attr-defined"

import pendulum as pnd  # simpler and more intuitive datetime library

import ultimate_notion as uno
from ultimate_notion.adapters import sync
from ultimate_notion.adapters.google import GTasksClient, SyncGTasks

######################################################
# Define a real simple Notion database for our tasks #
######################################################

PARENT_PAGE = 'Tests'  # Defines the page where the database should be created
today = pnd.datetime(2024, 1, 1, tz='UTC')


class Status(uno.OptionNS):
    backlog = uno.Option('Backlog', color=uno.Color.GRAY)
    in_progress = uno.Option('In Progress', color=uno.Color.BLUE)
    blocked = uno.Option('Blocked', color=uno.Color.RED)
    done = uno.Option('Done', color=uno.Color.GREEN)


class Task(uno.Schema, db_title='My synced task db'):
    """My personal task list of all the important stuff I have to do"""

    task = uno.Property('Task', uno.PropType.Title())
    status = uno.Property('Status', uno.PropType.Select(Status))
    due_date = uno.Property('Due Date', uno.PropType.Date())


with uno.Session() as notion:
    parent = notion.search_page(PARENT_PAGE).item()
    task_db = notion.get_or_create_db(parent=parent, schema=Task)

    if task_db.is_empty:
        Task.create(
            task='Clean the house',
            due_date=today.add(days=5),
            status=Status.in_progress,
        )

        Task.create(
            task='Try out Ultimate Notion',
            due_date=today.subtract(days=1),
            status=Status.done,
        )

        Task.create(
            task='On Notion Only',
            due_date=today.add(days=3),
            status=Status.done,
        )

#################################################
# Define a few tasks in a Google Tasks tasklist #
#################################################

with GTasksClient() as gtasks:
    tasklist = gtasks.get_or_create_tasklist('My synced task list')
    if tasklist.is_empty:
        tasklist.create_task('Clean the house', due=today.add(days=5))
        tasklist.create_task(
            'Try out Ultimate Notion', due=today.subtract(days=1)
        )
        tasklist.create_task('On Google Tasks only', due=today.add(days=1))

########################################################
# Create the synced task between Notion & Google Tasks #
########################################################

# Option 1: Using the Notion database declaration from above
with uno.Session() as notion, GTasksClient(read_only=False) as gtasks:
    task_db = notion.get_or_create_db(parent=parent, schema=Task)
    tasklist = gtasks.get_or_create_tasklist('My synced task list')

    sync_task = SyncGTasks(
        notion_db=task_db,
        tasklist=tasklist,
        completed_col=Task.status,
        completed_val=Status.done,
        not_completed_val=Status.backlog,
        due_col=Task.due_date,
    )
    # Schedule the sync task to run every second
    # Omit the `in_total` argument to run the task forever
    sync_task.run_every(seconds=1).in_total(times=2).schedule()

    # Run all scheduled tasks
    sync.run_all_tasks()


# Option 2: Using an existing Notion database that was created manually
with uno.Session() as notion, GTasksClient(read_only=False) as gtasks:
    task_db = notion.search_db('My synced task db').item()
    status_col = task_db.schema.get_prop('Status')
    due_date_col = task_db.schema.get_prop('Due Date')
    tasklist = gtasks.get_or_create_tasklist('My synced task list')

    sync_task = SyncGTasks(
        notion_db=task_db,
        tasklist=tasklist,
        completed_col=status_col,
        completed_val=status_col.type.options['Done'],
        not_completed_val=status_col.type.options['Backlog'],
        due_col=due_date_col,
    )
    sync_task.run_every(seconds=1).in_total(times=2).schedule()
    sync.run_all_tasks()

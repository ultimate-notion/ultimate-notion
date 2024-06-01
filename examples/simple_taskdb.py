"""This example demonstrates how to create a simple task list"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ultimate_notion import (
    Color,
    Option,
    OptionNS,
    PageSchema,
    Property,
    PropType,
    Session,
)

PARENT_PAGE = 'Tests'  # Defines the page where the database should be created
today = datetime.now(tz=ZoneInfo('Europe/Berlin'))


class Status(OptionNS):
    backlog = Option('Backlog', color=Color.GRAY)
    in_progress = Option('In Progress', color=Color.BLUE)
    blocked = Option('Blocked', color=Color.RED)
    done = Option('Done', color=Color.GREEN)


class Priority(OptionNS):
    high = Option('✹ High', color=Color.RED)
    medium = Option('✷ Medium', color=Color.YELLOW)
    low = Option('✶ Low', color=Color.GRAY)


# assembling the formula to show the urgency of the task
days_left = (
    'if(empty(prop("Due Date")), toNumber(""), '
    'dateBetween(prop("Due Date"), now(), "days"))'
)
weeks_left = f'(if((({days_left}) < 0), -1, 1)) * floor(abs(({days_left}) / 7))'
time_left = (
    f'if(empty(({days_left})), "", (((if((({days_left}) < 0), "-", "")) + '
    f'(if((({weeks_left}) == 0), "", (format(abs(({weeks_left}))) + "w")))) + '
    f'(if(((({days_left}) % 7) == 0), "", (format(abs(({days_left})) % 7) + '
    '"d")))))'
)
urgency = (
    'if(prop("Status") == "Done", "✅", (if(empty(prop("Due Date")), "", '
    '(if((formatDate(now(), "YWD") == formatDate(prop("Due Date"), "YWD")), '
    f'"🔹 Today", (if(now() > prop("Due Date"), "🔥 " + {time_left}, "🕐 " '
    f'+ {time_left})))))))'
)


class Task(PageSchema, db_title='My task list'):
    """My personal task list of all the important stuff I have to do"""

    task = Property('Task', PropType.Title())
    status = Property('Status', PropType.Select(Status))
    priority = Property('Priority', PropType.Select(Priority))
    urgency = Property('Urgency', PropType.Formula(urgency))
    due_date = Property('Due Date', PropType.Date())


with Session() as notion:
    parent = notion.search_page(PARENT_PAGE).item()
    task_db = notion.create_db(parent=parent, schema=Task)

    # just create 10 random tasks for demonstration
    Task.create(
        task='Plan vacation',
        due_date=today + timedelta(weeks=3, days=3),
        status=Status.backlog,
        priority=Priority.high,
    )
    Task.create(
        task='Read book about procastination',
        due_date=today + timedelta(weeks=2, days=2),
        status=Status.backlog,
        priority=Priority.medium,
    )
    Task.create(
        task='Clean the house',
        due_date=today + timedelta(days=5),
        status=Status.in_progress,
        priority=Priority.low,
    )
    Task.create(
        task='Build tool with Ultimate Notion',
        due_date=today + timedelta(days=1),
        status=Status.in_progress,
        priority=Priority.low,
    )
    Task.create(
        task='Complete project report for work',
        due_date=today,
        status=Status.in_progress,
        priority=Priority.medium,
    )
    Task.create(
        task='Call family',
        due_date=today - timedelta(days=1),
        status=Status.done,
        priority=Priority.low,
    )
    Task.create(
        task='Pay yearly utility bills',
        due_date=today - timedelta(days=5),
        status=Status.blocked,
        priority=Priority.high,
    )
    Task.create(
        task='Run first Marathon',
        due_date=today - timedelta(weeks=1, days=1),
        status=Status.done,
        priority=Priority.low,
    )
    Task.create(
        task='Clearing out the cellar',
        due_date=today - timedelta(weeks=2, days=2),
        status=Status.in_progress,
        priority=Priority.low,
    )

    task_db.fetch_all().show()

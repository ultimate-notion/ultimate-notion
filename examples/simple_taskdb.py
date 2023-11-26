"""This example demonstrates how to create a simple task list"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ultimate_notion import Color, ColType, Column, Option, OptionNS, PageSchema, Session

PARENT_PAGE = 'Tests'  # Defines where the database should be created
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
    '(if((prop("Due Date") > now()), (dateBetween(prop("Due Date"), now(), "days") + 1), '
    'dateBetween(prop("Due Date"), now(), "days"))))'
)
weeks_left = f'(if((({days_left}) < 0), -1, 1)) * floor(abs(({days_left}) / 7))'
time_left = (
    f'if(empty(({days_left})), "", (((if((({days_left}) < 0), "-", "")) + '
    f'(if((({weeks_left}) == 0), "", (format(abs(({weeks_left}))) + "w")))) + '
    f'(if(((({days_left}) % 7) == 0), "", (format(abs(({days_left})) % 7) + "d")))))'
)
urgency = (
    'if(prop("Status") == "Done", "✅", (if(empty(prop("Due Date")), "", '
    '(if((formatDate(now(), "YWD") == formatDate(prop("Due Date"), "YWD")), "🔹 Today", '
    f'(if(now() > prop("Due Date"), "🔥 " + {time_left}, "🕐 " + {time_left})))))))'
)


class Task(PageSchema, db_title='My task list'):
    """My personal task list of all the important stuff I have to do"""

    task = Column('Task', ColType.Title())
    status = Column('Status', ColType.Select(Status))
    priority = Column('Priority', ColType.Select(Priority))
    urgency = Column('Urgency', ColType.Formula(urgency))
    due_date = Column('Due Date', ColType.Date())


with Session() as notion:
    parent = notion.search_page(PARENT_PAGE).item()
    notion.create_db(parent=parent, schema=Task)

    Task.create(
        task='Plan vacation', due_date=today + timedelta(weeks=3, days=3), status=Status.backlog, priority=Priority.high
    )
    Task.create(
        task='Read book about procastination',
        due_date=today + timedelta(weeks=2, days=2),
        status=Status.backlog,
        priority=Priority.medium,
    )
    Task.create(
        task='Clean the house', due_date=today + timedelta(days=5), status=Status.in_progress, priority=Priority.low
    )
    Task.create(
        task='Clearing out the cellar',
        due_date=today + timedelta(days=1),
        status=Status.in_progress,
        priority=Priority.low,
    )
    Task.create(
        task='Complete project report for work', due_date=today, status=Status.in_progress, priority=Priority.medium
    )
    Task.create(task='Call family', due_date=today - timedelta(days=1), status=Status.done, priority=Priority.low)
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

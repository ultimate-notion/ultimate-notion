"""This example demonstrates how to create a simple task list"""

import pendulum as pnd  # simpler and more intuitive datetime library

import ultimate_notion as uno

PARENT_PAGE = 'Tests'  # Defines the page where the database should be created
today = pnd.now('Europe/Berlin')


class Status(uno.OptionNS):
    backlog = uno.Option('Backlog', color=uno.Color.GRAY)
    in_progress = uno.Option('In Progress', color=uno.Color.BLUE)
    blocked = uno.Option('Blocked', color=uno.Color.RED)
    done = uno.Option('Done', color=uno.Color.GREEN)


class Priority(uno.OptionNS):
    high = uno.Option('✹ High', color=uno.Color.RED)
    medium = uno.Option('✷ Medium', color=uno.Color.YELLOW)
    low = uno.Option('✶ Low', color=uno.Color.GRAY)


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


class Task(uno.Schema, db_title='My task list'):
    """My personal task list of all the important stuff I have to do"""

    task = uno.PropType.Title('Task')
    status = uno.PropType.Select('Status', options=Status)
    priority = uno.PropType.Select('Priority', options=Priority)
    urgency = uno.PropType.Formula('Urgency', formula=urgency)
    due_date = uno.PropType.Date('Due Date')


with uno.Session() as notion:
    parent = notion.search_page(PARENT_PAGE).item()
    task_db = notion.create_db(parent=parent, schema=Task)

    # just create 10 random tasks for demonstration
    Task.create(
        task='Plan vacation',
        due_date=today.add(weeks=3, days=3),
        status=Status.backlog,
        priority=Priority.high,
    )
    Task.create(
        task='Read book about procastination',
        due_date=today.add(weeks=2, days=2),
        status=Status.backlog,
        priority=Priority.medium,
    )
    Task.create(
        task='Clean the house',
        due_date=today.add(days=5),
        status=Status.in_progress,
        priority=Priority.low,
    )
    Task.create(
        task='Build tool with Ultimate Notion',
        due_date=today.add(days=1),
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
        due_date=today.subtract(days=1),
        status=Status.done,
        priority=Priority.low,
    )
    Task.create(
        task='Pay yearly utility bills',
        due_date=today.subtract(days=5),
        status=Status.blocked,
        priority=Priority.high,
    )
    Task.create(
        task='Run first Marathon',
        due_date=today.subtract(weeks=1, days=1),
        status=Status.done,
        priority=Priority.low,
    )
    Task.create(
        task='Clearing out the cellar',
        due_date=today.subtract(weeks=2, days=2),
        status=Status.in_progress,
        priority=Priority.low,
    )

    task_db.get_all_pages().show()

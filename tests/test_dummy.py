# ruff: noqa
# mypy: ignore-errors
# flake8: noqa
# pylint: skip-file
# pyright: reportGeneralTypeIssues=false

import ultimate_notion as uno


def test_dummy():
    notion = uno.Session.get_or_create()  # if NOTION_TOKEN is set in environment

    intro_page = notion.search_page('Getting Started').item()

    intro_page.show()

    # from IPython import embed; embed()
    task_view = notion.search_db('Task DB').item().get_all_pages()
    task = task_view.search_page('Run first Marathon').item()

    print(f'Task "{task.title}" was {task.props.status} on {task.props.due_date}')

    task.parent_db.schema.show()

    f'Task "{task.title}" was {task.props["Status"]} on {task.props["Due Date"]}'

    from datetime import datetime, timedelta

    old_due_date = task.props.due_date
    # assign a datetime Python object
    new_due_date_dt = datetime(2024, 1, 1, 12, 0) + timedelta(days=7)
    task.props.due_date = new_due_date_dt
    assert task.props.due_date.date() == new_due_date_dt.date()

    # reassign the old property value object
    task.props.due_date = old_due_date
    assert task.props.due_date == old_due_date

    options = {opt.name: opt for opt in task.parent_db.schema.status.type.options}

    task.props.status = options['In Progress']

    task.props.status = 'Blocked'

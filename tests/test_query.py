from __future__ import annotations

import time
from typing import cast

import pytest

import ultimate_notion as uno
from ultimate_notion import schema


@pytest.mark.vcr()
def test_query_new_task_db(new_task_db: uno.Database):
    all_pages = new_task_db.query.execute()
    assert len(all_pages) == 0

    status_col = 'Status'
    Task = new_task_db.schema  # noqa: N806
    status_options = cast(schema.Select, Task[status_col]).options

    task1 = Task.create(task='Task 1', status=status_options['Done'])
    task2 = Task.create(task='Task 2', status=status_options['Backlog'])

    while len(new_task_db.query.execute()) != 2:
        time.sleep(1)

    filter_cond = uno.prop(status_col) == status_options['Done']
    query = new_task_db.query.filter(filter_cond)
    query_result = query.execute()
    assert query_result.to_pages() == [task1]

    query_result = new_task_db.query.sort(uno.prop('Task').desc()).execute()
    assert query_result.to_pages() == [task2, task1]

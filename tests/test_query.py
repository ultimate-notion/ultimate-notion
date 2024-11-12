from __future__ import annotations

import time
from typing import cast

import pytest

import ultimate_notion as uno
from ultimate_notion import schema


def test_query_condition_associative_rule():
    cond = (uno.prop('Name') == 'John') & (uno.prop('Age') > 18)
    assert str(cond) == "(prop('Name') == 'John') & (prop('Age') > 18)"

    cond = uno.prop('Name') == 'John'
    cond &= uno.prop('Age') > 18
    assert str(cond) == "(prop('Name') == 'John') & (prop('Age') > 18)"

    cond = (uno.prop('Name') == 'John') & (uno.prop('Age') > 18) & (uno.prop('Points') >= 20)
    assert str(cond) == "(prop('Name') == 'John') & (prop('Age') > 18) & (prop('Points') >= 20)"

    cond = (uno.prop('Name') == 'John') & ((uno.prop('Age') > 18) & (uno.prop('Points') >= 20))
    assert str(cond) == "(prop('Name') == 'John') & (prop('Age') > 18) & (prop('Points') >= 20)"

    cond = (uno.prop('Name') == 'John') & ((uno.prop('Age') > 18) | (uno.prop('Points') >= 20))
    assert str(cond) == "(prop('Name') == 'John') & ((prop('Age') > 18) | (prop('Points') >= 20))"

    cond = ((uno.prop('Name') == 'John') & (uno.prop('Age') > 18)) & (
        (uno.prop('Points') >= 20) & (uno.prop('Status') == 'Active')
    )
    assert (
        str(cond)
        == "(prop('Name') == 'John') & (prop('Age') > 18) & (prop('Points') >= 20) & (prop('Status') == 'Active')"
    )

    cond = (uno.prop('Name') == 'John') | (uno.prop('Age') > 18)
    assert str(cond) == "(prop('Name') == 'John') | (prop('Age') > 18)"

    cond = uno.prop('Name') == 'John'
    cond |= uno.prop('Age') > 18
    assert str(cond) == "(prop('Name') == 'John') | (prop('Age') > 18)"

    cond = (uno.prop('Name') == 'John') | (uno.prop('Age') > 18) | (uno.prop('Points') >= 20)
    assert str(cond) == "(prop('Name') == 'John') | (prop('Age') > 18) | (prop('Points') >= 20)"

    cond = (uno.prop('Name') == 'John') | ((uno.prop('Age') > 18) | (uno.prop('Points') >= 20))
    assert str(cond) == "(prop('Name') == 'John') | (prop('Age') > 18) | (prop('Points') >= 20)"

    cond = (uno.prop('Name') == 'John') | ((uno.prop('Age') > 18) & (uno.prop('Points') >= 20))
    assert str(cond) == "(prop('Name') == 'John') | ((prop('Age') > 18) & (prop('Points') >= 20))"

    cond = ((uno.prop('Name') == 'John') | (uno.prop('Age') > 18)) | (
        (uno.prop('Points') >= 20) | (uno.prop('Status') == 'Active')
    )
    assert (
        str(cond)
        == "(prop('Name') == 'John') | (prop('Age') > 18) | (prop('Points') >= 20) | (prop('Status') == 'Active')"
    )


@pytest.mark.vcr()
def test_query_new_task_db(new_task_db: uno.Database):
    all_pages = new_task_db.query.execute()
    assert len(all_pages) == 0

    Task = new_task_db.schema  # noqa: N806
    status_col = 'Status'
    status_options = cast(schema.Select, Task[status_col]).options

    task1 = Task.create(task='Task 1', status=status_options['Done'], due_date='2024-01-01')
    task2 = Task.create(task='Task 2', status=status_options['Backlog'], due_date='2024-01-02')
    task3 = Task.create(task='Task 3', status=status_options['In Progress'], due_date='2024-01-03')

    while len(new_task_db.query.execute()) != 3:
        time.sleep(1)

    # Test equality condition
    filter_cond: uno.Condition = uno.prop(status_col) == status_options['Done']
    query = new_task_db.query.filter(filter_cond)
    query_result = query.execute()
    assert query_result.to_pages() == [task1]

    # Test sorting
    query_result = new_task_db.query.sort(uno.prop('Task').desc()).execute()
    assert query_result.to_pages() == [task2, task1]

    # Test inequality condition
    filter_cond = uno.prop(status_col) != status_options['Done']
    query = new_task_db.query.filter(filter_cond).sort(uno.prop('Created').asc())
    query_result = query.execute()
    assert query_result.to_pages() == [task2, task3]

    # Test greater than condition
    filter_cond = uno.prop('Task') > '2024-01-01'
    query = new_task_db.query.filter(filter_cond)
    query_result = query.execute()
    assert set(query_result.to_pages()) == {task2, task3}

    # Test less than condition
    filter_cond = uno.prop('Task') < '2024-01-02'
    query = new_task_db.query.filter(filter_cond)
    query_result = query.execute()
    assert query_result.to_pages() == [task1]

    # Test greater than or equal to condition
    filter_cond = uno.prop('Task') >= '2024-01-02'
    query = new_task_db.query.filter(filter_cond)
    query_result = query.execute()
    assert set(query_result.to_pages()) == {task2, task3}

    # Test less than or equal to condition
    filter_cond = uno.prop('Task') <= '2024-01-02'
    query = new_task_db.query.filter(filter_cond)
    query_result = query.execute()
    assert set(query_result.to_pages()) == {task1, task2}


#     # Test contains condition
#     filter_cond = uno.prop('Task').contains('Task')
#     query = new_task_db.query.filter(filter_cond)
#     query_result = query.execute()
#     assert set(query_result.to_pages()) == {task1, task2, task3}

#     # Test does not contain condition
#     filter_cond = uno.prop('Task').does_not_contain('1')
#     query = new_task_db.query.filter(filter_cond)
#     query_result = query.execute()
#     assert set(query_result.to_pages()) == {task2, task3}

#     # Test starts with condition
#     filter_cond = uno.prop('Task').starts_with('Task')
#     query = new_task_db.query.filter(filter_cond)
#     query_result = query.execute()
#     assert set(query_result.to_pages()) == {task1, task2, task3}

#     # Test ends with condition
#     filter_cond = uno.prop('Task').ends_with('1')
#     query = new_task_db.query.filter(filter_cond)
#     query_result = query.execute()
#     assert query_result.to_pages() == [task1]

#     # Test is empty condition
#     filter_cond = uno.prop('Task').is_empty()
#     query = new_task_db.query.filter(filter_cond)
#     query_result = query.execute()
#     assert query_result.to_pages() == []

#     # Test is not empty condition
#     filter_cond = uno.prop('Task').is_not_empty()
#     query = new_task_db.query.filter(filter_cond)
#     query_result = query.execute()
#     assert set(query_result.to_pages()) == {task1, task2, task3}

#     # Test date conditions
#     filter_cond = uno.prop('Created Time').this_week()
#     query = new_task_db.query.filter(filter_cond)
#     query_result = query.execute()
#     assert set(query_result.to_pages()) == {task1, task2, task3}

#     filter_cond = uno.prop('Created Time').past_week()
#     query = new_task_db.query.filter(filter_cond)
#     query_result = query.execute()
#     assert query_result.to_pages() == []

#     filter_cond = uno.prop('Created Time').next_week()
#     query = new_task_db.query.filter(filter_cond)
#     query_result = query.execute()
#     assert query_result.to_pages() == []

#     # Test sorting
#     query_result = new_task_db.query.sort(uno.prop('Task').desc()).execute()
#     assert query_result.to_pages() == [task3, task2, task1]

#     query_result = new_task_db.query.sort(uno.prop('Task').asc()).execute()
#     assert query_result.to_pages() == [task1, task2, task3]

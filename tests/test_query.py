from __future__ import annotations

import time
from typing import cast

import pendulum as pnd
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
    exp_str = "(prop('Name') == 'John') & (prop('Age') > 18) & (prop('Points') >= 20) & (prop('Status') == 'Active')"
    assert str(cond) == exp_str

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
    exp_str = "(prop('Name') == 'John') | (prop('Age') > 18) | (prop('Points') >= 20) | (prop('Status') == 'Active')"
    assert str(cond) == exp_str


def test_all_query_conditions():
    cond = (
        (uno.prop('Name') == 'John')
        & (uno.prop('Name') != 'Doe')
        & (uno.prop('Age') > 10)
        & (uno.prop('Age') < 20)
        & (uno.prop('Age') >= 11)
        & (uno.prop('Age') <= 19)
        & uno.prop('Hobbies').contains('Running')
        & (uno.prop('Hobbies').does_not_contain('Boxing'))
        & uno.prop('Religion').is_empty()
        & uno.prop('Ratio').is_not_empty()
        & uno.prop('Life').starts_with('Brith')
        & uno.prop('Life').ends_with('Death')
        & uno.prop('Birthday').this_week()
        & uno.prop('Birthday').past_week()
        & uno.prop('Birthday').next_week()
        & uno.prop('Birthday').next_month()
        & uno.prop('Birthday').past_month()
        & uno.prop('Birthday').next_year()
        & uno.prop('Birthday').past_year()
    )
    exp_str = (
        "(prop('Name') == 'John') & (prop('Name') != 'Doe') & (prop('Age') > 10) & (prop('Age') < 20) "
        "& (prop('Age') >= 11) & (prop('Age') <= 19) & prop('Hobbies').contains('Running') "
        "& prop('Hobbies').does_not_contain('Boxing') & prop('Religion').is_empty() "
        "& prop('Ratio').is_not_empty() & prop('Life').starts_with('Brith') & prop('Life').ends_with('Death') "
        "& prop('Birthday').this_week() & prop('Birthday').past_week() & prop('Birthday').next_week() "
        "& prop('Birthday').next_month() & prop('Birthday').past_month() & prop('Birthday').next_year() "
        "& prop('Birthday').past_year()"
    )
    assert str(cond) == exp_str


def test_property():
    prop = uno.prop('Name')
    assert str(prop) == "prop('Name')"

    assert hash(prop) != hash(uno.prop('Age'))
    assert hash(prop.asc()) != hash(prop.desc())

    assert str(prop.any) == "prop('Name').any"
    assert str(prop.every) == "prop('Name').every"
    assert str(prop.none) == "prop('Name').none"

    assert str(prop.any.is_empty()) == "prop('Name').any.is_empty()"
    assert str(prop.every != 'John') == "prop('Name').every != 'John'"


@pytest.mark.vcr()
def test_date_query(root_page: uno.Page, notion: uno.Session):
    class DB(uno.Schema, db_title='Date Query DB Test'):
        name = uno.Property('Name', uno.PropType.Title())
        date = uno.Property('Date', uno.PropType.Date())
        created = uno.Property('Created', uno.PropType.CreatedTime())
        last_edited = uno.Property('Last Edited', uno.PropType.LastEditedTime())

    db = notion.create_db(parent=root_page, schema=DB)
    now = pnd.now()
    page_no_date = db.create_page(name='no_date')
    page_tw = db.create_page(name='this week', date=now)
    page_pw = db.create_page(name='past week', date=now.subtract(weeks=1))
    page_pm = db.create_page(name='past month', date=now.subtract(months=1))
    page_py = db.create_page(name='past year', date=now.subtract(years=1))
    page_nw = db.create_page(name='next week', date=now.add(weeks=1))
    page_nm = db.create_page(name='next month', date=now.add(months=1))
    page_ny = db.create_page(name='next year', date=now.add(years=1))
    all_pages = {page_no_date, page_tw, page_pw, page_pm, page_py, page_nw, page_nm, page_ny}

    pages = db.query.filter(uno.prop('Date').is_empty()).execute().to_pages()
    assert set(pages) == {page_no_date}

    pages = db.query.filter(uno.prop('Date').is_not_empty()).execute().to_pages()
    assert set(pages) == {page_tw, page_pw, page_pm, page_py, page_nw, page_nm, page_ny}

    pages = db.query.filter(uno.prop('Date') == now).execute().to_pages()
    assert set(pages) == {page_tw}

    with pytest.raises(ValueError):  # as inequality is not supported for date
        pages = db.query.filter(uno.prop('Date') != now).execute().to_pages()

    pages = db.query.filter(uno.prop('Date') < now).execute().to_pages()
    assert set(pages) == {page_pw, page_pm, page_py}

    pages = db.query.filter(uno.prop('Date') <= now).execute().to_pages()
    assert set(pages) == {page_tw, page_pw, page_pm, page_py}

    pages = db.query.filter(uno.prop('Date') > now).execute().to_pages()
    assert set(pages) == {page_nw, page_nm, page_ny}

    pages = db.query.filter(uno.prop('Date') >= now).execute().to_pages()
    assert set(pages) == {page_tw, page_nw, page_nm, page_ny}

    pages = db.query.filter(uno.prop('Date').this_week()).execute().to_pages()
    assert set(pages) == {page_tw}

    pages = db.query.filter(uno.prop('Date').past_week()).execute().to_pages()
    assert set(pages) == {page_pw, page_tw}

    pages = db.query.filter(uno.prop('Date').past_month()).execute().to_pages()
    assert set(pages) == {page_pm, page_pw, page_tw}

    pages = db.query.filter(uno.prop('Date').past_year()).execute().to_pages()
    assert set(pages) == {page_py, page_pm, page_pw, page_tw}

    pages = db.query.filter(uno.prop('Date').next_week()).execute().to_pages()
    assert set(pages) == {page_tw, page_nw}

    pages = db.query.filter(uno.prop('Date').next_month()).execute().to_pages()
    assert set(pages) == {page_tw, page_nw, page_nm}

    pages = db.query.filter(uno.prop('Date').next_year()).execute().to_pages()
    assert set(pages) == {page_tw, page_nw, page_nm, page_ny}

    for prop_name in ('Created', 'Last Edited'):
        # We cannot really set those two props to a specific date, so we just test the conditions
        pages = db.query.filter(uno.prop(prop_name) <= now.add(minutes=5)).execute().to_pages()
        assert set(pages) == all_pages

        pages = db.query.filter(uno.prop(prop_name) <= now.subtract(minutes=5)).execute().to_pages()
        assert set(pages) == set()

        pages = db.query.filter(uno.prop(prop_name).this_week()).execute().to_pages()
        assert set(pages) == all_pages

        pages = db.query.filter(uno.prop(prop_name).is_empty()).execute().to_pages()
        assert set(pages) == set()

        pages = db.query.filter(uno.prop(prop_name) == now.subtract(minutes=5)).execute().to_pages()
        assert set(pages) == set()


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

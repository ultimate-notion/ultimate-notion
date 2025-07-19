from __future__ import annotations

from typing import cast

import pendulum as pnd
import pytest

import ultimate_notion as uno
from ultimate_notion import schema
from ultimate_notion.errors import FilterQueryError
from ultimate_notion.utils import parse_dt_str


def test_query_condition_associative_rule() -> None:
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


def test_all_query_conditions() -> None:
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


def test_property() -> None:
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
def test_date_query(root_page: uno.Page, notion: uno.Session) -> None:
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

    # Test schema.Date()
    prop_name = 'Date'
    query = db.query.filter(uno.prop(prop_name).is_empty())
    assert set(query.execute()) == {page_no_date}

    query = db.query.filter(uno.prop(prop_name).is_not_empty())
    assert set(query.execute()) == {page_tw, page_pw, page_pm, page_py, page_nw, page_nm, page_ny}

    query = db.query.filter(uno.prop(prop_name) == now)
    assert set(query.execute()) == {page_tw}

    with pytest.raises(ValueError):  # as inequality is not supported for date
        query = db.query.filter(uno.prop(prop_name) != now)
        query.execute()

    query = db.query.filter(uno.prop(prop_name) < now)
    assert set(query.execute()) == {page_pw, page_pm, page_py}

    query = db.query.filter(uno.prop(prop_name) <= now)
    assert set(query.execute()) == {page_tw, page_pw, page_pm, page_py}

    query = db.query.filter(uno.prop(prop_name) > now)
    assert set(query.execute()) == {page_nw, page_nm, page_ny}

    query = db.query.filter(uno.prop(prop_name) >= now)
    assert set(query.execute()) == {page_tw, page_nw, page_nm, page_ny}

    query = db.query.filter(uno.prop(prop_name).this_week())
    assert set(query.execute()) == {page_tw}

    query = db.query.filter(uno.prop(prop_name).past_week())
    assert set(query.execute()) == {page_pw, page_tw}

    query = db.query.filter(uno.prop(prop_name).past_month())
    assert set(query.execute()) == {page_pm, page_pw, page_tw}

    query = db.query.filter(uno.prop(prop_name).past_year())
    assert set(query.execute()) == {page_py, page_pm, page_pw, page_tw}

    query = db.query.filter(uno.prop(prop_name).next_week())
    assert set(query.execute()) == {page_tw, page_nw}

    query = db.query.filter(uno.prop(prop_name).next_month())
    assert set(query.execute()) == {page_tw, page_nw, page_nm}

    query = db.query.filter(uno.prop(prop_name).next_year())
    assert set(query.execute()) == {page_tw, page_nw, page_nm, page_ny}

    # Test schema.CreatedTime() and schema.LastEditedTime() conditions
    for prop_name in ('Created', 'Last Edited'):
        # We cannot really set those two props to a specific date, so we just test the conditions
        query = db.query.filter(uno.prop(prop_name) <= now.add(minutes=5))
        assert set(query.execute()) == all_pages

        query = db.query.filter(uno.prop(prop_name) <= now.subtract(minutes=5))
        assert set(query.execute()) == set()

        query = db.query.filter(uno.prop(prop_name).this_week())
        assert set(query.execute()) == all_pages

        query = db.query.filter(uno.prop(prop_name).is_empty())
        assert set(query.execute()) == set()

        query = db.query.filter(uno.prop(prop_name) == now.subtract(minutes=5))
        assert set(query.execute()) == set()


@pytest.mark.vcr()
def test_text_query(root_page: uno.Page, notion: uno.Session) -> None:
    class DB(uno.Schema, db_title='Text Query DB Test'):
        title = uno.Property('Title', uno.PropType.Title())
        name = uno.Property('Name', uno.PropType.Text())
        phone = uno.Property('Phone', uno.PropType.Phone())
        email = uno.Property('Email', uno.PropType.Email())
        url = uno.Property('URL', uno.PropType.URL())

    db = notion.create_db(parent=root_page, schema=DB)
    page_empty = db.create_page()
    page_john_doe = db.create_page(
        title='John', name='John Doe', phone='123-456-7890', email='john.doe@gmail.com', url='https://john.doe.com'
    )
    page_jane_doe = db.create_page(
        title='Jane', name='Jane Doe', phone='123-456-7890', email='jane.doe@gmail.com', url='https://jane.doe.de'
    )

    for prop_name in ('Title', 'Name', 'Phone', 'Email', 'URL'):
        query = db.query.filter(uno.prop(prop_name).is_empty())
        assert set(query.execute()) == {page_empty}

        query = db.query.filter(uno.prop(prop_name).is_not_empty())
        assert set(query.execute()) == {page_john_doe, page_jane_doe}

        query = db.query.filter(uno.prop(prop_name) == 'John Doe')
        if prop_name == 'Name':
            assert set(query.execute()) == {page_john_doe}
        else:
            assert set(query.execute()) == set()

        query = db.query.filter(uno.prop(prop_name) != 'John Doe')
        if prop_name == 'Name':
            assert set(query.execute()) == {page_jane_doe, page_empty}
        else:
            assert set(query.execute()) == {page_john_doe, page_jane_doe, page_empty}

        query = db.query.filter(uno.prop(prop_name).contains('Doe'))
        if prop_name in {'Name', 'Email', 'URL'}:
            assert set(query.execute()) == {page_john_doe, page_jane_doe}
        else:
            assert set(query.execute()) == set()

        query = db.query.filter(uno.prop(prop_name).does_not_contain('Doe'))
        if prop_name in {'Name', 'Email', 'URL'}:
            assert set(query.execute()) == {page_empty}
        else:
            assert set(query.execute()) == {page_john_doe, page_jane_doe, page_empty}

        query = db.query.filter(uno.prop(prop_name).starts_with('John'))
        if prop_name in {'Name', 'Title', 'Email'}:
            assert set(query.execute()) == {page_john_doe}
        else:
            assert set(query.execute()) == set()

        query = db.query.filter(uno.prop(prop_name).ends_with('Doe'))
        if prop_name == 'Name':
            assert set(query.execute()) == {page_john_doe, page_jane_doe}
        else:
            assert set(query.execute()) == set()


@pytest.mark.vcr()
def test_number_query(root_page: uno.Page, notion: uno.Session) -> None:
    class DB(uno.Schema, db_title='Number Query DB Test'):
        title = uno.Property('Title', uno.PropType.Title())
        number = uno.Property('Number', uno.PropType.Number())

    db = notion.create_db(parent=root_page, schema=DB)
    page_empty = db.create_page()
    page_1 = db.create_page(title='1', number=1)
    page_2 = db.create_page(title='1', number=2)
    page_42 = db.create_page(title='42', number=42)

    prop_name = 'Number'
    query = db.query.filter(uno.prop(prop_name).is_empty())
    assert set(query.execute()) == {page_empty}

    query = db.query.filter(uno.prop(prop_name).is_not_empty())
    assert set(query.execute()) == {page_1, page_2, page_42}

    query = db.query.filter(uno.prop(prop_name) == 42)
    assert set(query.execute()) == {page_42}

    query = db.query.filter(uno.prop(prop_name) != 42)
    assert set(query.execute()) == {page_1, page_2, page_empty}

    query = db.query.filter(uno.prop(prop_name) > 1)
    assert set(query.execute()) == {page_2, page_42}

    query = db.query.filter(uno.prop(prop_name) >= 1)
    assert set(query.execute()) == {page_1, page_2, page_42}

    query = db.query.filter(uno.prop(prop_name) < 42)
    assert set(query.execute()) == {page_1, page_2}

    query = db.query.filter(uno.prop(prop_name) <= 42)
    assert set(query.execute()) == {page_1, page_2, page_42}


@pytest.mark.vcr()
def test_select_query(root_page: uno.Page, notion: uno.Session) -> None:
    status_options = [
        backlog := uno.Option('Backlog', color=uno.Color.GRAY),
        ongoing := uno.Option('In Progress', color=uno.Color.BLUE),
        done := uno.Option('Done', color=uno.Color.GREEN),
    ]

    class DB(uno.Schema, db_title='(Multi)-Select Query DB Test'):
        title = uno.Property('Title', uno.PropType.Title())
        select = uno.Property('Select', uno.PropType.Select(status_options))
        multi_select = uno.Property('Multi-Select', uno.PropType.MultiSelect(status_options))

    db = notion.create_db(parent=root_page, schema=DB)
    page_empty = db.create_page()
    page_1 = db.create_page(title='Done', select=done, multi_select=[done, ongoing])
    page_2 = db.create_page(title='In Progress', select=ongoing, multi_select=[backlog, ongoing])
    page_3 = db.create_page(title='Backlog', select=backlog, multi_select=[backlog])

    # Test Select
    prop_name = 'Select'
    query = db.query.filter(uno.prop(prop_name).is_empty())
    assert set(query.execute()) == {page_empty}

    query = db.query.filter(uno.prop(prop_name).is_not_empty())
    assert set(query.execute()) == {page_1, page_2, page_3}

    query = db.query.filter(uno.prop(prop_name) == 'Done')
    assert set(query.execute()) == {page_1}

    query = db.query.filter(uno.prop(prop_name) != 'Done')
    assert set(query.execute()) == {page_2, page_3, page_empty}

    query = db.query.filter(uno.prop(prop_name) == done)
    assert set(query.execute()) == {page_1}

    query = db.query.filter(uno.prop(prop_name) != done)
    assert set(query.execute()) == {page_2, page_3, page_empty}

    # Test MultiSelect
    prop_name = 'Multi-Select'
    query = db.query.filter(uno.prop(prop_name).is_empty())
    assert set(query.execute()) == {page_empty}

    query = db.query.filter(uno.prop(prop_name).is_not_empty())
    assert set(query.execute()) == {page_1, page_2, page_3}

    query = db.query.filter(uno.prop(prop_name).contains('Done'))
    assert set(query.execute()) == {page_1}

    query = db.query.filter(uno.prop(prop_name).does_not_contain('Done'))
    assert set(query.execute()) == {page_2, page_3, page_empty}

    query = db.query.filter(uno.prop(prop_name).contains(done))
    assert set(query.execute()) == {page_1}

    query = db.query.filter(uno.prop(prop_name).does_not_contain(done))
    assert set(query.execute()) == {page_2, page_3, page_empty}


@pytest.mark.vcr()
def test_files_checkbox_query(root_page: uno.Page, notion: uno.Session) -> None:
    class DB(uno.Schema, db_title='Files & Checkbox Query DB Test'):
        title = uno.Property('Title', uno.PropType.Title())
        files = uno.Property('Files', uno.PropType.Files())
        check = uno.Property('Checkbox', uno.PropType.Checkbox())

    db = notion.create_db(parent=root_page, schema=DB)

    page_empty = db.create_page()

    page_files = db.create_page(
        title='Files', files=[uno.FileInfo(name='image', url='https://some-site.com/image.png')]
    )
    page_check = db.create_page(title='Checkbox', check=True)

    # Test Files
    prop_name = 'Files'
    query = db.query.filter(uno.prop(prop_name).is_empty())
    assert set(query.execute()) == {page_empty, page_check}

    query = db.query.filter(uno.prop(prop_name).is_not_empty())
    assert set(query.execute()) == {page_files}

    # Test Checkbox
    prop_name = 'Checkbox'
    query = db.query.filter(uno.prop(prop_name) == True)  # noqa: E712
    assert set(query.execute()) == {page_check}

    query = db.query.filter(uno.prop(prop_name) == False)  # noqa: E712
    assert set(query.execute()) == {page_empty, page_files}

    query = db.query.filter(uno.prop(prop_name) != False)  # noqa: E712
    assert set(query.execute()) == {page_check}

    query = db.query.filter(uno.prop(prop_name) != True)  # noqa: E712
    assert set(query.execute()) == {page_empty, page_files}


@pytest.mark.vcr()
def test_people_relation_query(root_page: uno.Page, notion: uno.Session, person: uno.User) -> None:
    class DB(uno.Schema, db_title='People & Relation Query DB Test'):
        title = uno.Property('Title', uno.PropType.Title())
        people = uno.Property('People', uno.PropType.Person())
        relation = uno.Property('Relation', uno.PropType.Relation(uno.SelfRef))

    db = notion.create_db(parent=root_page, schema=DB)

    page_empty = db.create_page()
    page_florian = db.create_page(title='Florian', people=[person])
    page_fan = db.create_page(title='Fan', relation=page_florian)

    # Test People
    prop_name = 'People'
    query = db.query.filter(uno.prop(prop_name).is_empty())
    assert set(query.execute()) == {page_empty, page_fan}

    query = db.query.filter(uno.prop(prop_name).is_not_empty())
    assert set(query.execute()) == {page_florian}

    query = db.query.filter(uno.prop(prop_name).contains(person))
    assert set(query.execute()) == {page_florian}

    query = db.query.filter(uno.prop(prop_name).does_not_contain(person))
    assert set(query.execute()) == {page_empty, page_fan}

    # Test Relation
    prop_name = 'Relation'
    query = db.query.filter(uno.prop(prop_name).is_empty())
    assert set(query.execute()) == {page_empty, page_florian}

    query = db.query.filter(uno.prop(prop_name).is_not_empty())
    assert set(query.execute()) == {page_fan}

    query = db.query.filter(uno.prop(prop_name).contains(page_florian))
    assert set(query.execute()) == {page_fan}

    query = db.query.filter(uno.prop(prop_name).does_not_contain(page_florian))
    assert set(query.execute()) == {page_empty, page_florian}


@pytest.mark.vcr()
def test_query_new_task_db(new_task_db: uno.Database) -> None:
    all_pages = new_task_db.query.execute()
    assert len(all_pages) == 0

    Task = new_task_db.schema  # noqa: N806
    status_col = 'Status'
    status_options = {option.name: option for option in cast(schema.Select, Task[status_col]).options}

    task1 = Task.create(task='Task 1', status=status_options['Done'], due_date='2024-01-01')
    task2 = Task.create(task='Task 2', status=status_options['Backlog'], due_date='2024-01-02')
    task3 = Task.create(task='Task 3', status=status_options['In Progress'], due_date='2024-01-01')

    assert str(new_task_db.query) == "Query(database='My Tasks', sort=(), filter=None)"

    query = new_task_db.query.sort(uno.prop('Due Date').asc(), uno.prop('Task').asc())
    assert set(query.execute()) == {task1, task3, task2}

    query = new_task_db.query.sort('Due Date', 'Task')
    assert set(query.execute()) == {task1, task3, task2}

    query = new_task_db.query.sort(uno.prop('Due Date').asc(), uno.prop('Task').desc())
    assert set(query.execute()) == {task3, task1, task2}

    query = new_task_db.query.filter(uno.prop('Due Date') == '2024-01-01').filter(uno.prop('Status') == 'Done')
    assert set(query.execute()) == {task1}

    query = new_task_db.query.filter((uno.prop('Due Date') == '2024-01-01') & (uno.prop('Status') == 'In Progress'))
    assert set(query.execute()) == {task3}

    query = new_task_db.query.filter((uno.prop('Due Date') == '2024-01-02') | (uno.prop('Status') == 'In Progress'))
    assert set(query.execute()) == {task2, task3}


@pytest.mark.vcr()
def test_query_formula(root_page: uno.Page, notion: uno.Session, formula_db: uno.Database) -> None:
    item_1, item_2 = formula_db.get_all_pages()
    query = formula_db.query.filter(uno.prop('String') == 'Item 1')
    assert set(query.execute()) == {item_1}

    query = formula_db.query.filter(uno.prop('Number') == 1)
    assert set(query.execute()) == {item_2}

    query = formula_db.query.filter(uno.prop('Checkbox') == True)  # noqa: E712
    assert set(query.execute()) == {item_1}

    query = formula_db.query.filter(uno.prop('Date') == parse_dt_str('2024-11-25 14:08:00+00:00'))
    assert set(query.execute()) == {item_1, item_2}

    query = formula_db.query.filter(uno.prop('String').contains('1'))
    assert set(query.execute()) == {item_1}

    query = formula_db.query.filter(uno.prop('String').starts_with('Item'))
    assert set(query.execute()) == {item_1, item_2}

    query = formula_db.query.filter(uno.prop('String').is_empty())
    assert set(query.execute()) == set()

    with pytest.raises(FilterQueryError):
        formula_db.query.filter(uno.prop('String') <= 69).execute()

    query = formula_db.query.filter(uno.prop('Number').is_empty())
    assert set(query.execute()) == set()

    with pytest.raises(FilterQueryError):
        formula_db.query.filter(uno.prop('Number').this_week()).execute()

    query = formula_db.query.filter(uno.prop('Date').is_empty())
    assert set(query.execute()) == set()

    query = formula_db.query.filter(uno.prop('Number') <= 42)
    assert set(query.execute()) == {item_1, item_2}

    with pytest.raises(FilterQueryError):
        formula_db.query.filter(uno.prop('Number').contains('42')).execute()

    with pytest.raises(FilterQueryError):
        formula_db.query.filter(uno.prop('Number').starts_with('42')).execute()

    query = formula_db.query.filter(uno.prop('Date') >= '2024-11-23')
    assert set(query.execute()) == {item_1, item_2}

    query = formula_db.query.filter(uno.prop('Date').next_week())
    assert set(query.execute()) == set()

    class DB(uno.Schema, db_title='Empty Formula DB Test'):
        title = uno.Property('Title', uno.PropType.Title())
        formula = uno.Property('Formula', uno.PropType.Formula('prop("Title")'))

    db = notion.create_db(parent=root_page, schema=DB)

    query = db.query.filter(uno.prop('Formula').is_empty())
    assert set(query.execute()) == set()


@pytest.mark.vcr()
def test_query_rollup(root_page: uno.Page, notion: uno.Session) -> None:
    rollup_title_prop = 'Rollup Title'
    rollup_number_prop = 'Rollup Number'
    rollup_number_prop_arr = 'Rollup Number Array'
    rollup_date_prop = 'Rollup Date'
    rollup_date_arr_prop = 'Rollup Date Array'

    class DB(uno.Schema, db_title='Rollup Query DB Test'):
        title = uno.Property('Title', uno.PropType.Title())
        relation = uno.Property('Relation', uno.PropType.Relation(uno.SelfRef))
        date = uno.Property('Date', uno.PropType.Date())
        number = uno.Property('Number', uno.PropType.Number())
        rollup_title = uno.Property(
            rollup_title_prop,
            uno.PropType.Rollup(relation=relation, rollup=title, calculate=uno.AggFunc.SHOW_ORIGINAL),
        )
        rollup_date = uno.Property(
            rollup_date_prop,
            uno.PropType.Rollup(relation=relation, rollup=date, calculate=uno.AggFunc.EARLIEST_DATE),
        )
        rollup_date_arr = uno.Property(
            rollup_date_arr_prop,
            uno.PropType.Rollup(relation=relation, rollup=date, calculate=uno.AggFunc.SHOW_ORIGINAL),
        )
        rollup_number = uno.Property(
            rollup_number_prop,
            uno.PropType.Rollup(relation=relation, rollup=number, calculate=uno.AggFunc.MAX),
        )
        rollup_number_arr = uno.Property(
            rollup_number_prop_arr,
            uno.PropType.Rollup(relation=relation, rollup=number, calculate=uno.AggFunc.SHOW_ORIGINAL),
        )

    db = notion.create_db(parent=root_page, schema=DB)
    item_1 = db.create_page(title='Item 1', number=42, date='2024-11-25 14:08:00+00:00')
    item_2 = db.create_page(title='Item 2', number=72, date='1981-11-23 08:02:00+01:00', relation=item_1)
    item_3 = db.create_page(title='Item 3', number=12, date='2024-11-25 14:08:00+00:00', relation=(item_1, item_2))

    # Array Rollup
    query = db.query.filter(uno.prop(rollup_title_prop).any == 'Item 1')
    assert set(query.execute()) == {item_2, item_3}

    query = db.query.filter(uno.prop(rollup_title_prop).any.contains('Item 1'))
    assert set(query.execute()) == {item_2, item_3}

    query = db.query.filter(uno.prop(rollup_title_prop).every.starts_with('Item'))
    assert set(query.execute()) == {item_2, item_3}

    query = db.query.filter(uno.prop(rollup_title_prop).none.is_empty())
    assert set(query.execute()) == {item_1, item_2, item_3}

    with pytest.raises(FilterQueryError):
        db.query.filter(uno.prop(rollup_title_prop).contains('Item 1')).execute()

    with pytest.raises(FilterQueryError):
        db.query.filter(uno.prop(rollup_title_prop).starts_with('Item 1')).execute()

    with pytest.raises(FilterQueryError):
        db.query.filter(uno.prop(rollup_title_prop).is_empty()).execute()

    with pytest.raises(FilterQueryError):
        db.query.filter(uno.prop(rollup_title_prop) <= 42).execute()

    with pytest.raises(FilterQueryError):
        db.query.filter(uno.prop(rollup_title_prop).this_week()).execute()

    with pytest.raises(FilterQueryError):
        db.query.filter(uno.prop(rollup_title_prop) == 42).execute()

    # Date Rollup
    query = db.query.filter(uno.prop(rollup_date_prop).is_empty())
    assert set(query.execute()) == {item_1}

    query = db.query.filter(uno.prop(rollup_date_prop) == '2024-11-25')
    assert set(query.execute()) == {item_2}

    query = db.query.filter(uno.prop(rollup_date_prop) < '2024-11-25')
    assert set(query.execute()) == {item_3}

    query = db.query.filter(uno.prop(rollup_date_prop).past_week())
    assert set(query.execute()) == set()

    query = db.query.filter(uno.prop(rollup_date_prop).any <= '1981-11-25')
    assert set(query.execute()) == {item_3}

    with pytest.raises(FilterQueryError):
        db.query.filter(uno.prop(rollup_date_prop).contains('1981')).execute()

    # Date Array Rollup
    query = db.query.filter(uno.prop(rollup_date_arr_prop).any.past_week())
    assert set(query.execute()) == set()

    # Number Rollup
    query = db.query.filter(uno.prop(rollup_number_prop).is_empty())
    assert set(query.execute()) == {item_1}

    query = db.query.filter(uno.prop(rollup_number_prop) == 42)
    assert set(query.execute()) == {item_2}

    query = db.query.filter(uno.prop(rollup_number_prop) > 42)
    assert set(query.execute()) == {item_3}

    with pytest.raises(FilterQueryError):
        db.query.filter(uno.prop(rollup_number_prop).this_week()).execute()

    with pytest.raises(FilterQueryError):
        db.query.filter(uno.prop(rollup_number_prop).starts_with('4')).execute()

    # Number Array Rollup
    query = db.query.filter(uno.prop(rollup_number_prop_arr).any <= 42)
    assert set(query.execute()) == {item_2, item_3}


@pytest.mark.vcr()
def test_id_prop(all_props_db: uno.Database) -> None:
    all_pages = all_props_db.get_all_pages()

    query = all_props_db.query.filter(uno.prop('ID') != 42)
    assert set(query.execute()) == set(all_pages)

    query = all_props_db.query.filter(uno.prop('ID') > -1)
    assert set(query.execute()) == set(all_pages)

from __future__ import annotations

import pendulum as pnd
import pytest

import ultimate_notion as uno


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

    # Test schema.Date()
    prop_name = 'Date'
    pages = db.query.filter(uno.prop(prop_name).is_empty()).execute().to_pages()
    assert set(pages) == {page_no_date}

    pages = db.query.filter(uno.prop(prop_name).is_not_empty()).execute().to_pages()
    assert set(pages) == {page_tw, page_pw, page_pm, page_py, page_nw, page_nm, page_ny}

    pages = db.query.filter(uno.prop(prop_name) == now).execute().to_pages()
    assert set(pages) == {page_tw}

    with pytest.raises(ValueError):  # as inequality is not supported for date
        pages = db.query.filter(uno.prop(prop_name) != now).execute().to_pages()

    pages = db.query.filter(uno.prop(prop_name) < now).execute().to_pages()
    assert set(pages) == {page_pw, page_pm, page_py}

    pages = db.query.filter(uno.prop(prop_name) <= now).execute().to_pages()
    assert set(pages) == {page_tw, page_pw, page_pm, page_py}

    pages = db.query.filter(uno.prop(prop_name) > now).execute().to_pages()
    assert set(pages) == {page_nw, page_nm, page_ny}

    pages = db.query.filter(uno.prop(prop_name) >= now).execute().to_pages()
    assert set(pages) == {page_tw, page_nw, page_nm, page_ny}

    pages = db.query.filter(uno.prop(prop_name).this_week()).execute().to_pages()
    assert set(pages) == {page_tw}

    pages = db.query.filter(uno.prop(prop_name).past_week()).execute().to_pages()
    assert set(pages) == {page_pw, page_tw}

    pages = db.query.filter(uno.prop(prop_name).past_month()).execute().to_pages()
    assert set(pages) == {page_pm, page_pw, page_tw}

    pages = db.query.filter(uno.prop(prop_name).past_year()).execute().to_pages()
    assert set(pages) == {page_py, page_pm, page_pw, page_tw}

    pages = db.query.filter(uno.prop(prop_name).next_week()).execute().to_pages()
    assert set(pages) == {page_tw, page_nw}

    pages = db.query.filter(uno.prop(prop_name).next_month()).execute().to_pages()
    assert set(pages) == {page_tw, page_nw, page_nm}

    pages = db.query.filter(uno.prop(prop_name).next_year()).execute().to_pages()
    assert set(pages) == {page_tw, page_nw, page_nm, page_ny}

    # Test schema.CreatedTime() and schema.LastEditedTime() conditions
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
def test_text_query(root_page: uno.Page, notion: uno.Session):
    class DB(uno.Schema, db_title='Text Query DB Test'):
        title = uno.Property('Title', uno.PropType.Title())
        name = uno.Property('Name', uno.PropType.Text())
        phone = uno.Property('Phone', uno.PropType.PhoneNumber())
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
        pages = db.query.filter(uno.prop(prop_name).is_empty()).execute().to_pages()
        assert set(pages) == {page_empty}

        pages = db.query.filter(uno.prop(prop_name).is_not_empty()).execute().to_pages()
        assert set(pages) == {page_john_doe, page_jane_doe}

        pages = db.query.filter(uno.prop(prop_name) == 'John Doe').execute().to_pages()
        if prop_name == 'Name':
            assert set(pages) == {page_john_doe}
        else:
            assert set(pages) == set()

        pages = db.query.filter(uno.prop(prop_name) != 'John Doe').execute().to_pages()
        if prop_name == 'Name':
            assert set(pages) == {page_jane_doe, page_empty}
        else:
            assert set(pages) == {page_john_doe, page_jane_doe, page_empty}

        pages = db.query.filter(uno.prop(prop_name).contains('Doe')).execute().to_pages()
        if prop_name in {'Name', 'Email', 'URL'}:
            assert set(pages) == {page_john_doe, page_jane_doe}
        else:
            assert set(pages) == set()

        pages = db.query.filter(uno.prop(prop_name).does_not_contain('Doe')).execute().to_pages()
        if prop_name in {'Name', 'Email', 'URL'}:
            assert set(pages) == {page_empty}
        else:
            assert set(pages) == {page_john_doe, page_jane_doe, page_empty}

        pages = db.query.filter(uno.prop(prop_name).starts_with('John')).execute().to_pages()
        if prop_name in {'Name', 'Title', 'Email'}:
            assert set(pages) == {page_john_doe}
        else:
            assert set(pages) == set()

        pages = db.query.filter(uno.prop(prop_name).ends_with('Doe')).execute().to_pages()
        if prop_name == 'Name':
            assert set(pages) == {page_john_doe, page_jane_doe}
        else:
            assert set(pages) == set()


@pytest.mark.vcr()
def test_number_query(root_page: uno.Page, notion: uno.Session):
    class DB(uno.Schema, db_title='Number Query DB Test'):
        title = uno.Property('Title', uno.PropType.Title())
        number = uno.Property('Number', uno.PropType.Number())

    db = notion.create_db(parent=root_page, schema=DB)
    page_empty = db.create_page()
    page_1 = db.create_page(title='1', number=1)
    page_2 = db.create_page(title='1', number=2)
    page_42 = db.create_page(title='42', number=42)

    prop_name = 'Number'
    pages = db.query.filter(uno.prop(prop_name).is_empty()).execute().to_pages()
    assert set(pages) == {page_empty}

    pages = db.query.filter(uno.prop(prop_name).is_not_empty()).execute().to_pages()
    assert set(pages) == {page_1, page_2, page_42}

    pages = db.query.filter(uno.prop(prop_name) == 42).execute().to_pages()
    assert set(pages) == {page_42}

    pages = db.query.filter(uno.prop(prop_name) != 42).execute().to_pages()
    assert set(pages) == {page_1, page_2, page_empty}

    pages = db.query.filter(uno.prop(prop_name) > 1).execute().to_pages()
    assert set(pages) == {page_2, page_42}

    pages = db.query.filter(uno.prop(prop_name) >= 1).execute().to_pages()
    assert set(pages) == {page_1, page_2, page_42}

    pages = db.query.filter(uno.prop(prop_name) < 42).execute().to_pages()
    assert set(pages) == {page_1, page_2}

    pages = db.query.filter(uno.prop(prop_name) <= 42).execute().to_pages()
    assert set(pages) == {page_1, page_2, page_42}


@pytest.mark.vcr()
def test_select_query(root_page: uno.Page, notion: uno.Session):
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
    pages = db.query.filter(uno.prop(prop_name).is_empty()).execute().to_pages()
    assert set(pages) == {page_empty}

    pages = db.query.filter(uno.prop(prop_name).is_not_empty()).execute().to_pages()
    assert set(pages) == {page_1, page_2, page_3}

    pages = db.query.filter(uno.prop(prop_name) == 'Done').execute().to_pages()
    assert set(pages) == {page_1}

    pages = db.query.filter(uno.prop(prop_name) != 'Done').execute().to_pages()
    assert set(pages) == {page_2, page_3, page_empty}

    pages = db.query.filter(uno.prop(prop_name) == done).execute().to_pages()
    assert set(pages) == {page_1}

    pages = db.query.filter(uno.prop(prop_name) != done).execute().to_pages()
    assert set(pages) == {page_2, page_3, page_empty}

    # Test MultiSelect
    prop_name = 'Multi-Select'
    pages = db.query.filter(uno.prop(prop_name).is_empty()).execute().to_pages()
    assert set(pages) == {page_empty}

    pages = db.query.filter(uno.prop(prop_name).is_not_empty()).execute().to_pages()
    assert set(pages) == {page_1, page_2, page_3}

    pages = db.query.filter(uno.prop(prop_name).contains('Done')).execute().to_pages()
    assert set(pages) == {page_1}

    pages = db.query.filter(uno.prop(prop_name).does_not_contain('Done')).execute().to_pages()
    assert set(pages) == {page_2, page_3, page_empty}

    pages = db.query.filter(uno.prop(prop_name).contains(done)).execute().to_pages()
    assert set(pages) == {page_1}

    pages = db.query.filter(uno.prop(prop_name).does_not_contain(done)).execute().to_pages()
    assert set(pages) == {page_2, page_3, page_empty}


@pytest.mark.vcr()
def test_files_checkbox_query(root_page: uno.Page, notion: uno.Session):
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
    pages = db.query.filter(uno.prop(prop_name).is_empty()).execute().to_pages()
    assert set(pages) == {page_empty, page_check}

    pages = db.query.filter(uno.prop(prop_name).is_not_empty()).execute().to_pages()
    assert set(pages) == {page_files}

    # Test Checkbox
    prop_name = 'Checkbox'
    pages = db.query.filter(uno.prop(prop_name) == True).execute().to_pages()  # noqa: E712
    assert set(pages) == {page_check}

    pages = db.query.filter(uno.prop(prop_name) == False).execute().to_pages()  # noqa: E712
    assert set(pages) == {page_empty, page_files}

    pages = db.query.filter(uno.prop(prop_name) != False).execute().to_pages()  # noqa: E712
    assert set(pages) == {page_check}

    pages = db.query.filter(uno.prop(prop_name) != True).execute().to_pages()  # noqa: E712
    assert set(pages) == {page_empty, page_files}


@pytest.mark.vcr()
def test_people_relation_query(root_page: uno.Page, notion: uno.Session, person: uno.User):
    class DB(uno.Schema, db_title='People & Relation Query DB Test'):
        title = uno.Property('Title', uno.PropType.Title())
        people = uno.Property('People', uno.PropType.People())
        relation = uno.Property('Relation', uno.PropType.Relation(uno.SelfRef))

    db = notion.create_db(parent=root_page, schema=DB)

    page_empty = db.create_page()
    page_florian = db.create_page(title='Florian', people=[person])
    page_fan = db.create_page(title='Fan', relation=page_florian)

    # Test People
    prop_name = 'People'
    pages = db.query.filter(uno.prop(prop_name).is_empty()).execute().to_pages()
    assert set(pages) == {page_empty, page_fan}

    pages = db.query.filter(uno.prop(prop_name).is_not_empty()).execute().to_pages()
    assert set(pages) == {page_florian}

    pages = db.query.filter(uno.prop(prop_name).contains(person)).execute().to_pages()
    assert set(pages) == {page_florian}

    pages = db.query.filter(uno.prop(prop_name).does_not_contain(person)).execute().to_pages()
    assert set(pages) == {page_empty, page_fan}

    # Test Relation
    prop_name = 'Relation'
    pages = db.query.filter(uno.prop(prop_name).is_empty()).execute().to_pages()
    assert set(pages) == {page_empty, page_florian}

    pages = db.query.filter(uno.prop(prop_name).is_not_empty()).execute().to_pages()
    assert set(pages) == {page_fan}

    pages = db.query.filter(uno.prop(prop_name).contains(page_florian)).execute().to_pages()
    assert set(pages) == {page_fan}

    pages = db.query.filter(uno.prop(prop_name).does_not_contain(page_florian)).execute().to_pages()
    assert set(pages) == {page_empty, page_florian}

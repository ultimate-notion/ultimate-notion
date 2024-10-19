"""Unit test for a View"""

from __future__ import annotations

import pytest

import ultimate_notion as uno


@pytest.mark.vcr()
def test_select(contacts_db: uno.Database):
    view = contacts_db.fetch_all()

    sub_view = view.select('Name', 'Role')
    assert sub_view.columns == ['Name', 'Role']

    sub_view = view.select('Role')
    assert sub_view.columns == ['Role']

    with pytest.raises(RuntimeError):
        view.select('Not included')


@pytest.mark.vcr()
def test_rows(contacts_db: uno.Database):
    view = contacts_db.fetch_all()
    rows = view.to_rows()
    assert len(rows) == len(view)
    view = view.select('Name', 'Role')
    row = view.get_row(0)
    assert len(row) == 2
    row = view.with_index().get_row(0)
    assert len(row) == 3


@pytest.mark.vcr()
def test_index(contacts_db: uno.Database):
    view = contacts_db.fetch_all()
    assert not view.has_index
    view = view.with_index('my_index')
    assert view.has_index
    idx = 1
    row = view.get_row(idx)
    assert row[0] == idx
    row = view.without_index().get_row(idx)
    assert row[0] != idx  # this is the title at that point
    view = view.with_index().with_index().without_index().without_index()
    assert not view.has_index


@pytest.mark.vcr()
def test_clone(contacts_db: uno.Database):
    view = contacts_db.fetch_all()
    assert len(view) == 10
    short_view = view.limit(3)
    assert len(short_view) == 3
    assert len(view) == 10


@pytest.mark.vcr()
def test_reverse(contacts_db: uno.Database):
    short_view = contacts_db.fetch_all().limit(3)
    row_0 = short_view.get_row(0)
    row_2 = short_view.get_row(2)
    rev_short_view = short_view.reverse()
    assert rev_short_view.get_row(0) == row_2
    assert rev_short_view.get_row(2) == row_0


@pytest.mark.vcr()
def test_to_pandas(task_db: uno.Database):
    view = task_db.fetch_all()
    df = view.to_pandas()
    assert len(view) == len(df)

"""Unit test for a View"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from ultimate_notion.database import Database


@pytest.mark.webtest
def test_select(contacts_db: Database):
    view = contacts_db.pages()
    sub_view = view.select('Name', 'Role')
    assert sub_view.columns == ['Name', 'Role']
    sub_view = view.select(['Name', 'Role'])
    assert sub_view.columns == ['Name', 'Role']
    sub_view = view.select(['Name'], 'Role')
    assert sub_view.columns == ['Name', 'Role']

    sub_view = view.select('Role')
    assert sub_view.columns == ['Role']

    with pytest.raises(RuntimeError):
        view.select('Not included')


@pytest.mark.webtest
def test_rows(contacts_db: Database):
    view = contacts_db.pages()
    rows = view.rows()
    assert len(rows) == len(view)
    view = view.select('Name', 'Role')
    row = view.row(0)
    assert len(row) == 2
    row = view.with_index().row(0)
    assert len(row) == 3


@pytest.mark.webtest
def test_index(contacts_db: Database):
    view = contacts_db.pages()
    assert not view.has_index
    view = view.with_index('my_index')
    assert view.has_index
    idx = 1
    row = view.row(idx)
    assert row[0] == idx
    row = view.without_index().row(idx)
    assert row[0].value != idx  # this is the title at that point
    view = view.with_index().with_index().without_index().without_index()
    assert not view.has_index

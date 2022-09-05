"""Unit tests for the Notional session."""

import pytest

from ultimate_notion.core import records
from ultimate_notion.utils import slist


@pytest.mark.vcr()
def test_session_raise_for_status(notion):
    """Verify the active session responds or raise."""
    assert notion.raise_for_status() is None


@pytest.mark.vcr()
def test_simple_search(notion):
    """Make sure search returns some results."""

    search = notion.search()

    num_results = 0

    for result in search.execute():
        assert isinstance(result, records.Record)
        num_results += 1

    # sanity check to make sure some results came back
    assert num_results > 0


@pytest.mark.vcr()
def test_search_db(notion, create_blank_db):
    dbs = notion.search_db("TestDB")
    assert isinstance(dbs, slist)

    with pytest.raises(ValueError):
        dbs.item()

    create_blank_db("TestDB")

    db = notion.search_db("TestDB").item()
    assert db.title == "TestDB"


@pytest.mark.vcr()
def test_get_db(notion, create_blank_db):
    create_blank_db("TestDB_for_id")
    db1 = notion.search_db("TestDB_for_id").item()

    db2 = notion.get_db(db1.id)  # as uuid
    assert db1.id == db2.id

    db2 = notion.get_db(str(db1.id))  # as str
    assert db1.id == db2.id
